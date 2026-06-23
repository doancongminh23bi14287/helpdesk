"""
SEO / Google Search Console integration endpoints.

Prefix: /api/seo/gsc
Auth: staff or admin only (except /callback — uses Redis state for CSRF)
Scoping: each org has at most one GscConnection; org access validated via assert_org_access.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config
from app.core.deps import get_current_user, require_staff_or_admin
from app.core.redis_client import redis_client
from app.core.scoping import assert_org_access
from app.database import get_db
from app.models.gsc_connection import GscConnection
from app.models.user import User

router = APIRouter(prefix="/api/seo/gsc", tags=["seo-gsc"])

_STATE_TTL = 600  # seconds (10 min) — time for user to complete OAuth flow


# ── internal helpers ──────────────────────────────────────────────────────────

def _conn_or_404(org_id: int, db: Session) -> GscConnection:
    conn = db.query(GscConnection).filter(GscConnection.org_id == org_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="No GSC connection for this organization")
    return conn


def _resolve_org(user: User, db: Session, org_id: Optional[int]) -> int:
    """Resolve target org_id (default to user's own org) and verify access."""
    target = org_id if org_id is not None else user.org_id
    assert_org_access(target, user, db)
    return target


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/connect")
def get_connect_url(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Return the Google OAuth2 consent URL. Frontend should redirect the user there."""
    from app.services import gsc as gsc_svc

    if not config.GSC_CLIENT_ID or not config.GSC_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GSC not configured on this server")

    target_org = _resolve_org(user, db, org_id)
    state = secrets.token_urlsafe(32)
    redis_client.setex(f"gsc_state:{state}", _STATE_TTL, f"{target_org}:{user.id}")

    url = gsc_svc.build_auth_url(state)
    return {"url": url, "org_id": target_org}


@router.get("/callback")
def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth2 redirect.
    Authentication here is via the state token stored in Redis (CSRF-safe).
    No Bearer token — this endpoint is called by Google's browser redirect.
    """
    from app.services import gsc as gsc_svc

    frontend_seo = f"{config.FRONTEND_URL}/seo"

    if error or not code or not state:
        return RedirectResponse(url=f"{frontend_seo}?gsc_error={error or 'cancelled'}")

    stored = redis_client.get(f"gsc_state:{state}")
    if not stored:
        return RedirectResponse(url=f"{frontend_seo}?gsc_error=invalid_state")
    redis_client.delete(f"gsc_state:{state}")

    try:
        val = stored.decode() if isinstance(stored, bytes) else stored
        org_id_s, user_id_s = val.split(":")
        org_id, user_id = int(org_id_s), int(user_id_s)
    except Exception:
        return RedirectResponse(url=f"{frontend_seo}?gsc_error=invalid_state")

    try:
        tokens = gsc_svc.exchange_code(code)
    except Exception:
        return RedirectResponse(url=f"{frontend_seo}?gsc_error=token_exchange_failed")

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return RedirectResponse(url=f"{frontend_seo}?gsc_error=no_refresh_token")

    access_token = tokens.get("access_token")
    expires_in = int(tokens.get("expires_in", 3600))
    expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)

    conn = db.query(GscConnection).filter(GscConnection.org_id == org_id).first()
    if conn:
        conn.refresh_token = refresh_token
        conn.access_token = access_token
        conn.token_expiry = expiry
        conn.connected_by = user_id
        conn.status = "connected"
    else:
        conn = GscConnection(
            org_id=org_id,
            refresh_token=refresh_token,
            access_token=access_token,
            token_expiry=expiry,
            connected_by=user_id,
            status="connected",
        )
        db.add(conn)
    db.commit()

    return RedirectResponse(url=f"{frontend_seo}?gsc_connected=1")


@router.get("/status")
def get_status(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Return connection status for the org. Never exposes token values."""
    configured = bool(config.GSC_CLIENT_ID and config.GSC_CLIENT_SECRET)
    target_org = _resolve_org(user, db, org_id)
    conn = db.query(GscConnection).filter(GscConnection.org_id == target_org).first()

    if not conn:
        return {"connected": False, "configured": configured, "org_id": target_org}

    connector = db.query(User).filter(User.id == conn.connected_by).first()
    return {
        "connected": True,
        "configured": configured,
        "org_id": target_org,
        "property_url": conn.property_url,
        "status": conn.status,
        "connected_by": connector.full_name if connector else None,
        "connected_at": conn.created_at.isoformat() if conn.created_at else None,
    }


@router.get("/properties")
def list_properties(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """List GSC properties verified for the connected Google account."""
    from app.services import gsc as gsc_svc

    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)

    try:
        token = gsc_svc.get_valid_token(conn, db)
        sites = gsc_svc.list_sites(token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GSC API error: {exc}")

    return {"properties": sites}


class PropertySelect(BaseModel):
    property_url: str


@router.post("/property")
def select_property(
    body: PropertySelect,
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Set the GSC property URL to track for this org."""
    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)
    conn.property_url = body.property_url
    db.commit()
    return {"property_url": conn.property_url}


@router.get("/search-analytics")
def search_analytics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    dimensions: str = Query("query"),
    row_limit: int = Query(100, ge=1, le=25000),
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """
    Query GSC Search Analytics.

    Defaults: last 28 days, dimension=query.
    Dimensions can be comma-separated: query,page,date,country,device.
    Response maps directly from GSC API (rows[].keys + clicks/impressions/ctr/position).
    """
    from datetime import date
    from app.services import gsc as gsc_svc

    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)

    if not conn.property_url:
        raise HTTPException(
            status_code=400,
            detail="No property selected. POST /api/seo/gsc/property first.",
        )

    today = date.today()
    end = end_date or today.isoformat()
    start = start_date or (today - timedelta(days=28)).isoformat()
    dim_list = [d.strip() for d in dimensions.split(",") if d.strip()]

    payload = {
        "startDate": start,
        "endDate": end,
        "dimensions": dim_list,
        "rowLimit": row_limit,
    }

    try:
        token = gsc_svc.get_valid_token(conn, db)
        data = gsc_svc.query_search_analytics(token, conn.property_url, payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GSC API error: {exc}")

    return data


@router.post("/disconnect")
def disconnect(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Remove the GSC connection for this org and revoke the token."""
    from app.services import gsc as gsc_svc

    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)

    if conn.access_token:
        gsc_svc.revoke_token(conn.access_token)

    db.delete(conn)
    db.commit()
    return {"disconnected": True, "org_id": target_org}
