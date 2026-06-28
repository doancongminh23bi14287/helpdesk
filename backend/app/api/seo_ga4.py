"""Google Analytics 4 OAuth2 + Data API endpoints."""
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import config
from app.core.deps import require_staff_or_admin
from app.core.redis_client import redis_client
from app.database import get_db
from app.models.ga4_connection import Ga4Connection
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo/ga4", tags=["ga4"])

_STATE_TTL = 600  # seconds


def _resolve_org(user: User, db: Session, org_id: Optional[int]) -> int:
    if user.role == "admin" and org_id:
        return org_id
    if user.org_id:
        return user.org_id
    raise HTTPException(status_code=400, detail="org_id required")


def _conn_or_404(org_id: int, db: Session) -> Ga4Connection:
    conn = db.query(Ga4Connection).filter(Ga4Connection.org_id == org_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="GA4 not connected")
    return conn


# ── 1. GET /connect ────────────────────────────────────────────────────────────

@router.get("/connect")
def get_connect_url(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    if not config.GSC_CLIENT_ID or not config.GSC_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GA4_CLIENT_ID / GA4_CLIENT_SECRET not configured")

    target_org = _resolve_org(user, db, org_id)
    state = secrets.token_urlsafe(32)
    redis_client.setex(f"ga4:state:{state}", _STATE_TTL, str(target_org))

    from app.services import ga4 as ga4_svc
    url = ga4_svc.build_auth_url(state)
    return {"url": url}


# ── 2. GET /callback ───────────────────────────────────────────────────────────

@router.get("/callback")
def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    frontend_base = config.CORS_ORIGINS[0] if config.CORS_ORIGINS else "http://localhost:5173"

    if error or not code or not state:
        return RedirectResponse(f"{frontend_base}/seo?ga4_error={error or 'missing_params'}")

    org_id_raw = redis_client.get(f"ga4:state:{state}")
    if not org_id_raw:
        return RedirectResponse(f"{frontend_base}/seo?ga4_error=invalid_state")
    redis_client.delete(f"ga4:state:{state}")

    org_id = int(org_id_raw)
    from app.services import ga4 as ga4_svc
    try:
        tokens = ga4_svc.exchange_code(code)
    except Exception as exc:
        logger.warning("GA4 token exchange failed: %s", exc)
        return RedirectResponse(f"{frontend_base}/seo?ga4_error=token_exchange_failed")

    from datetime import datetime, timedelta, timezone
    expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=int(tokens.get("expires_in", 3600)))

    conn = db.query(Ga4Connection).filter(Ga4Connection.org_id == org_id).first()
    if conn:
        conn.refresh_token = tokens["refresh_token"]
        conn.access_token = tokens.get("access_token")
        conn.token_expiry = expiry
        conn.status = "connected"
    else:
        conn = Ga4Connection(
            org_id=org_id,
            refresh_token=tokens["refresh_token"],
            access_token=tokens.get("access_token"),
            token_expiry=expiry,
        )
        db.add(conn)
    db.commit()

    return RedirectResponse(f"{frontend_base}/seo?ga4_connected=1")


# ── 3. GET /status ─────────────────────────────────────────────────────────────

@router.get("/status")
def get_status(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    target_org = _resolve_org(user, db, org_id)
    conn = db.query(Ga4Connection).filter(Ga4Connection.org_id == target_org).first()
    if not conn:
        return {"connected": False, "configured": bool(config.GSC_CLIENT_ID)}
    return {
        "connected": True,
        "property_id": conn.property_id,
        "property_name": conn.property_name,
        "configured": True,
    }


# ── 4. GET /properties ─────────────────────────────────────────────────────────

@router.get("/properties")
def list_properties(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)

    from app.services import ga4 as ga4_svc
    try:
        token = ga4_svc.get_valid_token(conn, db)
        props = ga4_svc.list_properties(token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GA4 API error: {exc}")

    return {"properties": props}


# ── 5. POST /property ──────────────────────────────────────────────────────────

from pydantic import BaseModel

class PropertySelect(BaseModel):
    property_id: str
    property_name: str = ""


@router.post("/property")
def select_property(
    body: PropertySelect,
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)
    conn.property_id = body.property_id.replace("properties/", "")
    conn.property_name = body.property_name
    db.commit()
    return {"property_id": conn.property_id, "property_name": conn.property_name}


# ── 6. GET /report ─────────────────────────────────────────────────────────────

@router.get("/report")
def get_report(
    start_date: str = Query("30daysAgo"),
    end_date: str = Query("today"),
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)

    if not conn.property_id:
        raise HTTPException(status_code=400, detail="No GA4 property selected. POST /api/seo/ga4/property first.")

    from app.services import ga4 as ga4_svc
    try:
        token = ga4_svc.get_valid_token(conn, db)

        # Summary metrics
        summary_resp = ga4_svc.run_report(token, conn.property_id, {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "metrics": [
                {"name": "sessions"},
                {"name": "totalUsers"},
                {"name": "engagementRate"},
                {"name": "averageSessionDuration"},
            ],
        })

        # Daily sessions for sparkline
        daily_resp = ga4_svc.run_report(token, conn.property_id, {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "dimensions": [{"name": "date"}],
            "metrics": [{"name": "sessions"}],
            "orderBys": [{"dimension": {"dimensionName": "date"}}],
        })

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GA4 API error: {exc}")

    # Parse summary
    summary = {"sessions": 0, "users": 0, "engagementRate": 0.0, "avgSessionDuration": 0.0}
    if summary_resp.get("rows"):
        vals = summary_resp["rows"][0]["metricValues"]
        summary = {
            "sessions": int(float(vals[0]["value"])),
            "users": int(float(vals[1]["value"])),
            "engagementRate": round(float(vals[2]["value"]) * 100, 1),
            "avgSessionDuration": round(float(vals[3]["value"]), 1),
        }

    # Parse sparkline
    sparkline = []
    for row in daily_resp.get("rows", []):
        date_str = row["dimensionValues"][0]["value"]
        sessions = int(float(row["metricValues"][0]["value"]))
        sparkline.append({"date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}", "v": sessions})

    return {
        "summary": summary,
        "sparkline": sparkline,
        "property_id": conn.property_id,
        "property_name": conn.property_name,
    }


# ── 7. DELETE /disconnect ──────────────────────────────────────────────────────

@router.delete("/disconnect")
def disconnect(
    org_id: Optional[int] = Query(None),
    user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    target_org = _resolve_org(user, db, org_id)
    conn = _conn_or_404(target_org, db)

    from app.services import ga4 as ga4_svc
    if conn.access_token:
        ga4_svc.revoke_token(conn.access_token)

    db.delete(conn)
    db.commit()
    return {"disconnected": True}
