# backend/app/api/tickets.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional

from app.database import get_db
from app.models.ticket import Ticket, TicketActivity, TicketReply
from app.models.service import Service
from app.models.team import StaffOrgAssignment
from app.models.user import User
from app.core.deps import get_current_user, require_admin, require_staff_or_admin
from app.schemas.ticket import TicketCreate, TicketUpdate, TicketOut, TicketDetailOut

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

VALID_TRANSITIONS = {
    "Open": ["In Progress"],
    "In Progress": ["Waiting", "Resolved"],
    "Waiting": ["In Progress", "Resolved"],
    "Resolved": ["Closed", "In Progress"],
    "Closed": ["Open"],
}


def _get_ticket_in_scope(ticket_id: int, user: User, db: Session) -> Ticket:
    """Return ticket if user can access it. Raises 404 if not found or out of scope."""
    base = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False)

    if user.role == "admin":
        ticket = base.first()
    elif user.role == "staff":
        assigned = (
            select(StaffOrgAssignment.org_id)
            .where(StaffOrgAssignment.user_id == user.id)
            .scalar_subquery()
        )
        ticket = base.filter(
            (Ticket.org_id.in_(assigned)) | (Ticket.assignee_id == user.id)
        ).first()
    else:  # customer
        ticket = base.filter(Ticket.org_id == user.org_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


# ── POST /api/tickets ─────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=TicketOut)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Customers can only raise tickets for their own org
    if user.role == "customer" and payload.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Cannot create ticket for another organization")

    # Validate that service_id belongs to the declared org
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if not service or service.org_id != payload.org_id:
        raise HTTPException(status_code=422, detail="Service does not belong to the specified organization")

    ticket = Ticket(
        org_id=payload.org_id,
        service_id=payload.service_id,
        subject=payload.subject,
        description=payload.description,
        priority=payload.priority,
        ticket_type=payload.ticket_type,
        status="Open",
        source="portal",
        raised_by=user.id,
        raised_by_email=user.email,
    )
    db.add(ticket)
    db.flush()  # get ticket.id without committing

    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=user.id,
        action="created",
    )
    db.add(activity)
    db.commit()
    db.refresh(ticket)
    return ticket


# ── GET /api/tickets ──────────────────────────────────────────────────────────

@router.get("", response_model=List[TicketOut])
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    org_id: Optional[int] = None,
    service_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Ticket).filter(Ticket.is_deleted == False)  # noqa: E712

    # Role-based scoping
    if user.role == "admin":
        pass  # no restriction
    elif user.role == "staff":
        assigned = (
            select(StaffOrgAssignment.org_id)
            .where(StaffOrgAssignment.user_id == user.id)
            .scalar_subquery()
        )
        query = query.filter(
            (Ticket.org_id.in_(assigned)) | (Ticket.assignee_id == user.id)
        )
    else:  # customer
        query = query.filter(Ticket.org_id == user.org_id)

    # Optional filters
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if org_id:
        query = query.filter(Ticket.org_id == org_id)
    if service_id:
        query = query.filter(Ticket.service_id == service_id)

    return query.order_by(Ticket.created_at.desc()).all()


# ── GET /api/tickets/{id} ─────────────────────────────────────────────────────

@router.get("/{ticket_id}", response_model=TicketDetailOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)

    # Fetch replies (customers only see non-internal)
    replies_query = db.query(TicketReply).filter(TicketReply.ticket_id == ticket_id)
    if user.role == "customer":
        replies_query = replies_query.filter(TicketReply.is_internal == False)  # noqa: E712
    replies = replies_query.order_by(TicketReply.created_at.asc()).all()

    # Fetch activities
    activities = (
        db.query(TicketActivity)
        .filter(TicketActivity.ticket_id == ticket_id)
        .order_by(TicketActivity.created_at.asc())
        .all()
    )

    # Build response manually (TicketDetailOut uses from_attributes)
    ticket_dict = {
        "id": ticket.id,
        "org_id": ticket.org_id,
        "service_id": ticket.service_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "ticket_type": ticket.ticket_type,
        "source": ticket.source,
        "raised_by": ticket.raised_by,
        "raised_by_email": ticket.raised_by_email,
        "assignee_id": ticket.assignee_id,
        "is_deleted": ticket.is_deleted,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "replies": replies,
        "activities": activities,
    }
    return TicketDetailOut.model_validate(ticket_dict)


# ── PUT /api/tickets/{id} ─────────────────────────────────────────────────────

@router.put("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)

    changes = payload.model_dump(exclude_none=True)

    if "status" in changes:
        new_status = changes["status"]
        current_status = ticket.status
        allowed = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status transition from '{current_status}' to '{new_status}'",
            )
        activity = TicketActivity(
            ticket_id=ticket.id,
            actor_id=user.id,
            action="status_change",
            from_value=current_status,
            to_value=new_status,
        )
        db.add(activity)
        ticket.status = new_status

    if "priority" in changes:
        old_priority = ticket.priority
        new_priority = changes["priority"]
        activity = TicketActivity(
            ticket_id=ticket.id,
            actor_id=user.id,
            action="priority_change",
            from_value=old_priority,
            to_value=new_priority,
        )
        db.add(activity)
        ticket.priority = new_priority

    if "assignee_id" in changes:
        old_assignee = str(ticket.assignee_id) if ticket.assignee_id else None
        new_assignee = str(changes["assignee_id"]) if changes["assignee_id"] else None
        activity = TicketActivity(
            ticket_id=ticket.id,
            actor_id=user.id,
            action="assigned",
            from_value=old_assignee,
            to_value=new_assignee,
        )
        db.add(activity)
        ticket.assignee_id = changes["assignee_id"]

    db.commit()
    db.refresh(ticket)
    return ticket


# ── DELETE /api/tickets/{id} ──────────────────────────────────────────────────

@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.is_deleted == False,  # noqa: E712
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.is_deleted = True
    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=user.id,
        action="deleted",
    )
    db.add(activity)
    db.commit()
    return {"message": "Ticket deleted"}
