# backend/app/api/admin.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime as _dt
from pydantic import BaseModel, ConfigDict
from app.database import get_db
from app.models.user import User
from app.models.sla import SlaPolicy
from app.models.ticket import Ticket, TicketActivity
from app.models.invoice import Invoice
from app.core.deps import require_admin
from app.services.email_piping import process_inbox

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/email/poll")
def manual_email_poll(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    count = process_inbox(db)
    return {"processed": count}


class SlaPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    priority: str
    response_hours: float
    resolution_hours: float


class SlaPolicyUpdate(BaseModel):
    response_hours: Optional[float] = None
    resolution_hours: Optional[float] = None


class ActivityItem(BaseModel):
    id: int
    ticket_id: int
    description: str
    created_at: _dt


class ActivityResponse(BaseModel):
    activities: list[ActivityItem]


class HealthResponse(BaseModel):
    overdue_invoices: int
    sla_breached_tickets: int
    celery_workers: str


_PRIORITY_ORDER = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}


@router.get("/sla/policies", response_model=List[SlaPolicyOut])
def list_sla_policies(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    policies = db.query(SlaPolicy).all()
    return sorted(policies, key=lambda p: _PRIORITY_ORDER.get(p.priority, 99))


@router.put("/sla/policies/{policy_id}", response_model=SlaPolicyOut)
def update_sla_policy(
    policy_id: int,
    payload: SlaPolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    policy = db.query(SlaPolicy).filter(SlaPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(policy, k, v)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/activity", response_model=ActivityResponse)
def get_recent_activity(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    activities = (
        db.query(TicketActivity)
        .order_by(TicketActivity.created_at.desc())
        .limit(10)
        .all()
    )

    actor_ids = {a.actor_id for a in activities if a.actor_id is not None}
    users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()}

    result = []
    for activity in activities:
        if activity.actor_id is not None:
            actor_user = users_by_id.get(activity.actor_id)
            actor_display = actor_user.email if actor_user else "System"
        else:
            actor_display = "System"

        action = activity.action
        ticket_id = activity.ticket_id

        if action == "created":
            description = f"{actor_display} created ticket #{ticket_id}"
        elif action == "status_change":
            description = (
                f"{actor_display} changed ticket #{ticket_id} status "
                f"from {activity.from_value} to {activity.to_value}"
            )
        elif action == "priority_change":
            description = (
                f"{actor_display} changed ticket #{ticket_id} priority to {activity.to_value}"
            )
        elif action in ("assigned", "auto_assigned"):
            description = f"{actor_display} assigned ticket #{ticket_id}"
        elif action == "replied":
            description = f"{actor_display} replied to ticket #{ticket_id}"
        else:
            description = f"{actor_display} updated ticket #{ticket_id}"

        result.append(
            {
                "id": activity.id,
                "ticket_id": ticket_id,
                "description": description,
                "created_at": activity.created_at,
            }
        )

    return {"activities": result}


@router.get("/health", response_model=HealthResponse)
def get_health(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    overdue_invoices = (
        db.query(Invoice).filter(Invoice.status == "overdue").count()
    )

    sla_breached_tickets = (
        db.query(Ticket)
        .filter(Ticket.sla_state == "breached", Ticket.is_deleted == False)
        .count()
    )

    try:
        from app.tasks.celery_app import celery_app as _celery_app
        result = _celery_app.control.inspect(timeout=1).ping()
        celery_workers = "running" if result else "stopped"
    except Exception as exc:
        logger.warning("Celery health check failed: %s", exc)
        celery_workers = "unknown"

    return {
        "overdue_invoices": overdue_invoices,
        "sla_breached_tickets": sla_breached_tickets,
        "celery_workers": celery_workers,
    }
