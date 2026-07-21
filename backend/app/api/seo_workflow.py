from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi import BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import require_staff_or_admin
from app.core.scoping import assert_org_access
from app.database import get_db
from app.models.service import Service
from app.models.gsc_connection import GscConnection
from app.models.user import User
from app.services.seo_opportunities import OpportunityThresholds, detect_opportunities

router = APIRouter(prefix="/api/seo", tags=["seo-workflow"])

class OpportunityTicketRequest(BaseModel):
    org_id: int
    rule_type: str = Field(min_length=1, max_length=60)
    target: Optional[str] = Field(default=None, max_length=1000)
    period: str = Field(min_length=1, max_length=40)
    current: dict = {}
    previous: Optional[dict] = None
    threshold: object = None
    evidence: str = Field(min_length=1, max_length=1000)
    recommended_action: str = Field(min_length=1, max_length=500)
    service_id: Optional[int] = None

@router.post("/opportunities/ticket", status_code=201)
def opportunity_to_ticket(payload: OpportunityTicketRequest, request: Request, user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    assert_org_access(payload.org_id, user, db)
    if payload.service_id is not None:
        service = db.query(Service).filter(Service.id == payload.service_id, Service.org_id == payload.org_id).first()
        if not service or service.is_archived:
            raise HTTPException(status_code=404, detail="Service not found")
    target = payload.target or "site performance"
    description = ("SEO monitoring signal for staff review.\n\n" f"Target: {target}\nPeriod: {payload.period}\n"
                   f"Rule: {payload.rule_type}\nCurrent metrics: {payload.current}\nPrevious metrics: {payload.previous or 'Not available'}\n"
                   f"Threshold: {payload.threshold}\nEvidence: {payload.evidence}\nSuggested review action: {payload.recommended_action}")
    from app.api.tickets import create_ticket
    from app.schemas.ticket import TicketCreate
    return create_ticket(request, TicketCreate(org_id=payload.org_id, service_id=payload.service_id,
        subject=f"SEO review: {target}"[:300], description=description, priority="Medium",
        ticket_type="SEO Request", assignment_mode="auto"), BackgroundTasks(), db, user)

@router.post("/opportunities/evaluate")
def evaluate_opportunity(payload: dict):
    allowed = {k: v for k, v in payload.get("thresholds", {}).items() if k in OpportunityThresholds.__dataclass_fields__}
    return {"opportunities": detect_opportunities(payload.get("current", {}), payload.get("previous"), OpportunityThresholds(**allowed), payload.get("target"), payload.get("period"))}


def _gsc_summary(rows):
    rows = rows or []
    clicks = sum(float(row.get("clicks", 0) or 0) for row in rows)
    impressions = sum(float(row.get("impressions", 0) or 0) for row in rows)
    positions = [float(row["position"]) for row in rows if row.get("position") is not None]
    return {"clicks": clicks, "impressions": impressions,
            "ctr": clicks / impressions if impressions else None,
            "average_position": sum(positions) / len(positions) if positions else None}


@router.get("/gsc/dashboard")
def gsc_dashboard(period: int = Query(28, enum=[7, 28, 90]), org_id: Optional[int] = Query(None),
                  user: User = Depends(require_staff_or_admin), db: Session = Depends(get_db)):
    """Return a bounded live GSC report for the scoped organisation."""
    from app.api.seo_gsc import _resolve_org
    from app.services import gsc as gsc_svc
    target_org = _resolve_org(user, db, org_id)
    conn = db.query(GscConnection).filter(GscConnection.org_id == target_org).first()
    if not conn or not conn.property_url:
        raise HTTPException(status_code=404, detail="No GSC property selected")
    try:
        token = gsc_svc.get_valid_token(conn, db)
        sites = gsc_svc.list_sites(token)
        if not any((site.get("siteUrl") or "").rstrip("/") == conn.property_url.rstrip("/") for site in sites):
            raise HTTPException(status_code=404, detail="GSC property is not available to this connection")
        today = date.today()
        current_start = today - timedelta(days=period - 1)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period - 1)
        def query(start, end, dimensions, limit):
            return gsc_svc.query_search_analytics(token, conn.property_url, {
                "startDate": start.isoformat(), "endDate": end.isoformat(),
                "dimensions": dimensions, "rowLimit": limit,
            }).get("rows", [])
        current = query(current_start, today, [], 1)
        previous = query(previous_start, previous_end, [], 1)
        top_queries = query(current_start, today, ["query"], 100)
        top_pages = query(current_start, today, ["page"], 100)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="GSC provider unavailable")
    return {"org_id": target_org, "property_url": conn.property_url, "period_days": period,
            "current": _gsc_summary(current), "previous": _gsc_summary(previous),
            "top_queries": top_queries, "top_pages": top_pages,
            "generated_at": today.isoformat()}
