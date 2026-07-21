from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import require_staff_or_admin
from app.core.scoping import assert_org_access
from app.database import get_db
from app.models.service import Service
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
