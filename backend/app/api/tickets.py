# backend/app/api/tickets.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from typing import List, Optional
from math import ceil

from app.database import get_db
from app.models.ticket import Ticket, TicketActivity, TicketReply
from app.models.attachment import TicketAttachment
from app.models.organization import Organization
from app.models.service import Service
from app.models.team import StaffOrgAssignment
from app.models.user import User
from app.core.deps import get_current_user, require_admin, require_staff_or_admin
from app.schemas.ticket import TicketCreate, TicketUpdate, TicketOut, TicketDetailOut, TicketReplyCreate, TicketReplyOut, TicketAssignPayload, AttachmentOut
from app.services.auto_assign import find_best_assignee, score_breakdown
from app.services.notify import create_notification
from app.services.sla_monitor import compute_sla_timestamps, get_sla_status
from app.services.file_storage import save_attachment, get_attachment_path

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

VALID_TICKET_SORT_FIELDS = {"created_at", "updated_at", "priority", "status"}


def _enrich_tickets(tickets: list, db: Session):
    """Attach org/service denormalized fields to each ticket object (in-place)."""
    org_ids = {t.org_id for t in tickets}
    svc_ids = {t.service_id for t in tickets if t.service_id}
    orgs = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()}
    svcs = {s.id: s for s in db.query(Service).filter(Service.id.in_(svc_ids)).all()} if svc_ids else {}
    for t in tickets:
        org = orgs.get(t.org_id)
        svc = svcs.get(t.service_id) if t.service_id else None
        t.org_name = org.name if org else None
        t.org_code = org.code if org else None
        t.service_name = svc.name if svc else None
        t.service_type = svc.type if svc else None
        t.service_status = svc.status if svc else None
    return tickets

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

    compute_sla_timestamps(ticket, db)

    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=user.id,
        action="created",
    )
    db.add(activity)

    # Auto-assign if no explicit assignee
    if ticket.assignee_id is None:
        best_id = find_best_assignee(ticket, db)
        if best_id:
            ticket.assignee_id = best_id
            assign_activity = TicketActivity(
                ticket_id=ticket.id,
                actor_id=None,  # system
                action="auto_assigned",
                to_value=str(best_id),
            )
            db.add(assign_activity)
            create_notification(
                db,
                user_id=best_id,
                title=f"Ticket #{ticket.id} auto-assigned to you",
                content=ticket.subject,
                type="assignment",
                ref_ticket_id=ticket.id,
            )

    db.commit()
    db.refresh(ticket)

    # Send email notification (fire and forget — don't block API)
    try:
        from app.tasks.email_sender_task import send_email_async
        org = db.query(Organization).filter(Organization.id == ticket.org_id).first()
        svc = db.query(Service).filter(Service.id == ticket.service_id).first() if ticket.service_id else None
        from app import config as _cfg
        subject = f"[#{ticket.id}] {ticket.subject}"
        ticket_url = f"http://localhost:5173/tickets/{ticket.id}"
        body_html = f"""<html><body style="font-family:Arial,sans-serif;color:#333">
<h2>New Support Ticket #{ticket.id}</h2>
<table><tr><td><b>Subject</b></td><td>{ticket.subject}</td></tr>
<tr><td><b>Org</b></td><td>{org.name if org else 'N/A'}</td></tr>
<tr><td><b>Service</b></td><td>{svc.name if svc else 'N/A'}</td></tr>
<tr><td><b>Priority</b></td><td>{ticket.priority}</td></tr>
<tr><td><b>Raised by</b></td><td>{ticket.raised_by_email or 'N/A'}</td></tr>
</table><p><a href="{ticket_url}">View Ticket</a></p></body></html>"""
        body_text = f"New ticket #{ticket.id}: {ticket.subject}\nPriority: {ticket.priority}\n{ticket_url}"
        send_email_async.delay(_cfg.ADMIN_NOTIFICATION_EMAIL, subject, body_html, body_text)
    except Exception:
        pass  # email failure must never break ticket creation

    return ticket


# ── GET /api/tickets ──────────────────────────────────────────────────────────

@router.get("")
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    org_id: Optional[int] = None,
    service_id: Optional[int] = None,
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
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

    # Search filter
    if search:
        term = f"%{search}%"
        query = query.filter(or_(
            Ticket.subject.ilike(term),
            Ticket.ticket_number.ilike(term),
        ))

    # Sort
    if sort not in VALID_TICKET_SORT_FIELDS:
        sort = "created_at"
    sort_col = getattr(Ticket, sort, Ticket.created_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    total = query.count()
    tickets = query.offset((page - 1) * per_page).limit(per_page).all()
    enriched = _enrich_tickets(tickets, db)
    return {
        "items": enriched,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


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

    # Lookup org/service names
    org = db.query(Organization).filter(Organization.id == ticket.org_id).first()
    svc = db.query(Service).filter(Service.id == ticket.service_id).first() if ticket.service_id else None

    ticket_dict = {
        "id": ticket.id,
        "org_id": ticket.org_id,
        "org_name": org.name if org else None,
        "org_code": org.code if org else None,
        "service_id": ticket.service_id,
        "service_name": svc.name if svc else None,
        "service_type": svc.type if svc else None,
        "service_status": svc.status if svc else None,
        "service_expiry_date": svc.expiry_date if svc else None,
        "service_monthly_cost": float(svc.monthly_cost) if svc and svc.monthly_cost else None,
        "service_disk_usage": svc.disk_usage if svc else None,
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

        # SLA pause/resume
        now_utc = datetime.utcnow()
        if new_status == "Waiting" and ticket.sla_paused_at is None:
            ticket.sla_paused_at = now_utc
        elif new_status == "In Progress" and ticket.sla_paused_at is not None:
            pause_duration = now_utc - ticket.sla_paused_at
            if ticket.resolution_by:
                ticket.resolution_by = ticket.resolution_by + pause_duration
            if ticket.response_by:
                ticket.response_by = ticket.response_by + pause_duration
            ticket.sla_paused_at = None

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

    # Email for significant status changes
    try:
        if "status" in changes and changes["status"] in ("Resolved", "Closed"):
            from app.tasks.email_sender_task import send_email_async
            raised_user = db.query(User).filter(User.id == ticket.raised_by).first() if ticket.raised_by else None
            to_email = ticket.raised_by_email or (raised_user.email if raised_user else None)
            if to_email:
                new_status = changes["status"]
                ticket_url = f"http://localhost:5173/tickets/{ticket.id}"
                subject = f"[#{ticket.id}] Status changed to {new_status}"
                body_html = f"""<html><body style="font-family:Arial,sans-serif;color:#333">
<h2>Ticket #{ticket.id} — {new_status}</h2>
<p>Your ticket <strong>{ticket.subject}</strong> status: <strong>{new_status}</strong></p>
<p><a href="{ticket_url}">View Ticket</a></p></body></html>"""
                body_text = f"Ticket #{ticket.id} '{ticket.subject}' → {new_status}\n{ticket_url}"
                send_email_async.delay(to_email, subject, body_html, body_text)
    except Exception:
        pass

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


# ── POST /api/tickets/{id}/replies ────────────────────────────────────────────

@router.post("/{ticket_id}/replies", status_code=201, response_model=TicketReplyOut)
def add_reply(
    ticket_id: int,
    payload: TicketReplyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)

    # Customers cannot post internal replies
    is_internal = (payload.is_internal is True) and (user.role != "customer")

    reply = TicketReply(
        ticket_id=ticket_id,
        author_id=user.id,
        author_email=user.email,
        content=payload.content,
        is_internal=is_internal,
        source="portal",
    )
    db.add(reply)

    # AUTO-REOPEN: if customer replies on Waiting or Resolved, reopen to In Progress
    if user.role == "customer" and ticket.status in ("Waiting", "Resolved"):
        old_status = ticket.status
        # Resume SLA if coming back from Waiting
        if old_status == "Waiting" and ticket.sla_paused_at is not None:
            pause_duration = datetime.utcnow() - ticket.sla_paused_at
            if ticket.resolution_by:
                ticket.resolution_by = ticket.resolution_by + pause_duration
            if ticket.response_by:
                ticket.response_by = ticket.response_by + pause_duration
            ticket.sla_paused_at = None
        ticket.status = "In Progress"
        reopen_activity = TicketActivity(
            ticket_id=ticket_id,
            actor_id=user.id,
            action="status_change",
            from_value=old_status,
            to_value="In Progress",
            detail="auto-reopened by customer reply",
        )
        db.add(reopen_activity)

    # Log replied activity
    reply_activity = TicketActivity(
        ticket_id=ticket_id,
        actor_id=user.id,
        action="replied",
    )
    db.add(reply_activity)

    # Notify the other party
    if user.role == "customer" and ticket.assignee_id:
        create_notification(
            db,
            user_id=ticket.assignee_id,
            title=f"New reply on Ticket #{ticket_id}",
            content=payload.content[:100],
            type="reply",
            ref_ticket_id=ticket_id,
        )
    elif user.role != "customer" and ticket.raised_by:
        create_notification(
            db,
            user_id=ticket.raised_by,
            title=f"New reply on Ticket #{ticket_id}",
            content=payload.content[:100],
            type="reply",
            ref_ticket_id=ticket_id,
        )

    db.commit()
    db.refresh(reply)

    # Email notification for reply
    try:
        if not is_internal:
            from app.tasks.email_sender_task import send_email_async
            ticket_url = f"http://localhost:5173/tickets/{ticket_id}"
            subject = f"Re: [#{ticket_id}] {ticket.subject}"
            body_html = f"""<html><body style="font-family:Arial,sans-serif;color:#333">
<h2>New Reply on Ticket #{ticket_id}</h2>
<p><b>{ticket.subject}</b></p>
<div style="background:#f9fafb;padding:12px;border-left:3px solid #1a56db;margin:16px 0">{payload.content[:500]}</div>
<p><a href="{ticket_url}">View Ticket</a></p></body></html>"""
            body_text = f"New reply on #{ticket_id}: {ticket.subject}\n\n{payload.content[:200]}\n{ticket_url}"
            if user.role == "customer" and ticket.assignee_id:
                assignee = db.query(User).filter(User.id == ticket.assignee_id).first()
                if assignee and assignee.email:
                    send_email_async.delay(assignee.email, subject, body_html, body_text)
            elif user.role != "customer" and ticket.raised_by_email:
                send_email_async.delay(ticket.raised_by_email, subject, body_html, body_text)
    except Exception:
        pass

    return reply


# ── POST /api/tickets/{id}/assign ────────────────────────────────────────────

@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(
    ticket_id: int,
    payload: TicketAssignPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Customers cannot assign tickets")
    ticket = _get_ticket_in_scope(ticket_id, user, db)
    # Admin can assign anyone; staff can only self-assign
    if user.role == "staff" and payload.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="Staff can only self-assign")
    old_assignee_id = ticket.assignee_id
    ticket.assignee_id = payload.assignee_id
    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=user.id,
        action="assigned",
        from_value=str(old_assignee_id) if old_assignee_id else None,
        to_value=str(payload.assignee_id),
    )
    db.add(activity)
    if payload.assignee_id != old_assignee_id:
        create_notification(
            db,
            user_id=payload.assignee_id,
            title=f"Ticket #{ticket.id} assigned to you",
            content=ticket.subject,
            type="assignment",
            ref_ticket_id=ticket.id,
        )
    db.commit()
    db.refresh(ticket)
    return ticket


# ── GET /api/tickets/{id}/assignment-score ────────────────────────────────────

@router.get("/{ticket_id}/assignment-score")
def get_assignment_score(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)
    return score_breakdown(ticket, db)


# ── GET /api/tickets/{id}/sla ─────────────────────────────────────────────────

@router.get("/{ticket_id}/sla")
def get_ticket_sla(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)
    return get_sla_status(ticket)


# ── GET /api/tickets/{id}/replies ─────────────────────────────────────────────

@router.get("/{ticket_id}/replies", response_model=List[TicketReplyOut])
def list_replies(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_ticket_in_scope(ticket_id, user, db)  # scope check — 404 if not accessible

    query = db.query(TicketReply).filter(TicketReply.ticket_id == ticket_id)
    if user.role == "customer":
        query = query.filter(TicketReply.is_internal == False)  # noqa: E712
    return query.order_by(TicketReply.created_at.asc()).all()


# ── POST /api/tickets/{id}/attachments ────────────────────────────────────────

@router.post("/{ticket_id}/attachments", status_code=201, response_model=AttachmentOut)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)
    org_id = ticket.org_id

    file_data = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    original_name = file.filename or "upload"

    rel_path, file_size = save_attachment(file_data, org_id, original_name, mime_type)

    attachment = TicketAttachment(
        ticket_id=ticket_id,
        reply_id=None,
        file_name=original_name[:255],
        file_path=rel_path,
        file_size=file_size,
        mime_type=mime_type[:100],
        uploaded_by=user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


# ── GET /api/tickets/{id}/attachments ─────────────────────────────────────────

@router.get("/{ticket_id}/attachments", response_model=List[AttachmentOut])
def list_attachments(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_ticket_in_scope(ticket_id, user, db)
    attachments = (
        db.query(TicketAttachment)
        .filter(TicketAttachment.ticket_id == ticket_id)
        .order_by(TicketAttachment.created_at.asc())
        .all()
    )
    return attachments
