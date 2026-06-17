# backend/app/api/tickets.py
from datetime import datetime, timezone
from typing import List, Optional
from math import ceil

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, File, UploadFile, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.ticket import Ticket, TicketAssignee, TicketActivity, TicketReply
from app.models.attachment import TicketAttachment
from app.models.organization import Organization
from app.models.service import Service
from app.models.notification import EmailLog
from app.models.email_thread import EmailThread
from app.models.project import ProjectDocument
from app.models.user import User
from app.core.deps import get_current_user, require_admin, require_staff_or_admin
from app.core.scoping import get_ticket_in_scope, scope_tickets
from app.core.limiter import limiter
from app import config
from app.schemas.ticket import TicketCreate, TicketUpdate, TicketOut, TicketDetailOut, TicketReplyCreate, TicketReplyOut, TicketAssignPayload, AttachmentOut, LinkProjectPayload
from app.services.auto_assign import find_best_assignee, score_breakdown
from app.services.assignment import set_ticket_assignees, load_assignees_for_tickets
from app.services.notify import create_notification
from app.services.sla_monitor import compute_sla_timestamps, get_sla_status
from app.services.file_storage import save_attachment, delete_attachment

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

VALID_TICKET_SORT_FIELDS = {"created_at", "updated_at", "priority", "status"}


def _resolve_reply_author(r, authors: dict) -> dict:
    """Build a serializable dict for a TicketReply with author_name resolved from User records."""
    if r.author_id and r.author_id in authors:
        a = authors[r.author_id]
        name = a.full_name or a.email.split('@')[0]
    elif r.author_email:
        name = r.author_email.split('@')[0]
    else:
        name = ''
    return {
        "id": r.id,
        "ticket_id": r.ticket_id,
        "author_id": r.author_id,
        "author_email": r.author_email,
        "author_name": name,
        "content": r.content,
        "is_internal": r.is_internal,
        "source": r.source,
        "created_at": r.created_at,
    }


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

def _ticket_out_dict(ticket: Ticket, db: Session) -> dict:
    """Build a TicketOut-compatible dict, including multi-assignee data."""
    assignees_map = load_assignees_for_tickets(db, [ticket.id])
    assignees = assignees_map.get(ticket.id, [])
    primary = next((a for a in assignees if a["is_primary"]), None)
    primary_user_id = primary["user_id"] if primary else ticket.assignee_id
    # Resolve primary user info if not already from assignees list
    if primary:
        p_name = primary["full_name"]
        p_email = primary["email"]
    elif primary_user_id:
        u = db.query(User).filter(User.id == primary_user_id).first()
        p_name = u.full_name if u else None
        p_email = u.email if u else None
    else:
        p_name = p_email = None

    return {
        "id": ticket.id,
        "org_id": ticket.org_id,
        "org_name": getattr(ticket, "org_name", None),
        "org_code": getattr(ticket, "org_code", None),
        "service_id": ticket.service_id,
        "project_id": ticket.project_id,
        "task_id": ticket.task_id,
        "task_title": getattr(ticket, "task_title", None),
        "service_name": getattr(ticket, "service_name", None),
        "service_type": getattr(ticket, "service_type", None),
        "service_status": getattr(ticket, "service_status", None),
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "ticket_type": ticket.ticket_type,
        "source": ticket.source,
        "raised_by": ticket.raised_by,
        "raised_by_email": ticket.raised_by_email,
        "assignee_id": ticket.assignee_id,
        "assignee_name": p_name,
        "assignee_email": p_email,
        "assignment_mode": ticket.assignment_mode,
        "assignees": assignees,
        "is_deleted": ticket.is_deleted,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }


VALID_TRANSITIONS = {
    "Open": ["In Progress"],
    "In Progress": ["Waiting", "Resolved"],
    "Waiting": ["In Progress", "Resolved"],
    "Resolved": ["Closed", "In Progress"],
    "Closed": ["Open"],
}


def _get_ticket_in_scope(ticket_id: int, user: User, db: Session) -> Ticket:
    """Return ticket if user can access it. Raises 404 if not found or out of scope."""
    return get_ticket_in_scope(ticket_id, user, db)


# ── POST /api/tickets ─────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=TicketOut)
@limiter.limit(config.RATE_LIMIT_TICKET_CREATE)
def create_ticket(
    request: Request,
    payload: TicketCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Customers can only raise tickets for their own org
    if user.role == "customer" and payload.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Cannot create ticket for another organization")

    # Validate service belongs to org (only when service_id is provided)
    if payload.service_id is not None:
        service = db.query(Service).filter(Service.id == payload.service_id).first()
        if not service or service.org_id != payload.org_id:
            raise HTTPException(status_code=422, detail="Service does not belong to the specified organization")

    # Validate project belongs to same org (when project_id is provided)
    if payload.project_id is not None:
        from app.models.project import Project
        project = db.query(Project).filter(Project.id == payload.project_id).first()
        if not project or project.org_id != payload.org_id:
            raise HTTPException(status_code=422, detail="Project does not belong to the specified organization")

    # Validate task_id and auto-set project_id if needed
    eff_project_id = payload.project_id
    if payload.task_id is not None:
        from app.models.project import ProjectTask
        task_obj = db.query(ProjectTask).filter(ProjectTask.id == payload.task_id).first()
        if not task_obj:
            raise HTTPException(status_code=422, detail="Task not found")
        if eff_project_id is None:
            eff_project_id = task_obj.project_id
        elif task_obj.project_id != eff_project_id:
            raise HTTPException(status_code=422, detail="Task does not belong to the specified project")

    # Append requested-item note to description when customer picks a catalogue item
    eff_description = payload.description
    if payload.requested_item_id is not None:
        from app.models.item import Item as CatalogueItem
        req_item = db.query(CatalogueItem).filter(
            CatalogueItem.id == payload.requested_item_id,
            CatalogueItem.is_active == True,
        ).first()
        if not req_item:
            raise HTTPException(status_code=422, detail="Requested item not found or inactive")
        eff_description = (payload.description or "") + f"\n\n[Gói khách quan tâm: {req_item.name} ({req_item.code})]"

    # Resolve effective assignee_ids and assignment_mode
    eff_ids: list[int] = []
    if payload.assignee_ids:
        eff_ids = list(payload.assignee_ids)
    elif payload.assignee_id is not None:
        eff_ids = [payload.assignee_id]

    eff_mode = payload.assignment_mode
    if eff_mode is None:
        eff_mode = "manual" if eff_ids else "auto"

    ticket = Ticket(
        org_id=payload.org_id,
        service_id=payload.service_id,
        project_id=eff_project_id,
        task_id=payload.task_id,
        subject=payload.subject,
        description=eff_description,
        priority=payload.priority,
        ticket_type=payload.ticket_type,
        status="Open",
        source="portal",
        raised_by=user.id,
        raised_by_email=user.email,
        assignment_mode=eff_mode,
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

    if eff_mode == "none":
        pass  # intentionally unassigned
    elif eff_mode == "manual" and eff_ids:
        set_ticket_assignees(db, ticket, eff_ids, assigned_by=user.id)
        if ticket.assignee_id:
            create_notification(
                db,
                user_id=ticket.assignee_id,
                title=f"Ticket #{ticket.id} assigned to you",
                content=ticket.subject,
                type="assignment",
                ref_ticket_id=ticket.id,
            )
    else:
        # Auto-assign
        best_id = find_best_assignee(ticket, db)
        if best_id:
            set_ticket_assignees(db, ticket, [best_id], assigned_by=None)
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
            # Stamp the winner so the tie-breaker stays accurate next time.
            assigned_user = db.query(User).filter(User.id == best_id).first()
            if assigned_user:
                assigned_user.last_assigned_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ticket)

    # Send email notifications in background (fire and forget — don't block API)
    try:
        from app.services.email_sender import bg_notify_new_ticket
        org = db.query(Organization).filter(Organization.id == ticket.org_id).first()
        svc = db.query(Service).filter(Service.id == ticket.service_id).first() if ticket.service_id else None
        background_tasks.add_task(
            bg_notify_new_ticket,
            ticket.id,
            org.name if org else None,
            svc.name if svc else None,
        )
    except Exception:
        pass  # email failure must never break ticket creation

    # Socket.IO: notify admin users of new ticket
    try:
        from app.socketio_server import notify_user
        admin_users = db.query(User).filter(User.role == "admin", User.is_active == True).all()
        event_data = {"ticket_id": ticket.id, "subject": ticket.subject}
        for admin_user in admin_users:
            background_tasks.add_task(notify_user, admin_user.id, "new_ticket", event_data)
    except Exception:
        pass

    return _ticket_out_dict(ticket, db)


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
    query = scope_tickets(query, user, db)

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
            Ticket.description.ilike(term),
        ))

    # Sort
    if sort not in VALID_TICKET_SORT_FIELDS:
        sort = "created_at"
    sort_col = getattr(Ticket, sort, Ticket.created_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    total = query.count()
    tickets = query.offset((page - 1) * per_page).limit(per_page).all()
    enriched = _enrich_tickets(tickets, db)

    ticket_ids = [t.id for t in enriched]
    assignees_by_id = load_assignees_for_tickets(db, ticket_ids)

    items = []
    for t in enriched:
        assignees = assignees_by_id.get(t.id, [])
        primary = next((a for a in assignees if a["is_primary"]), None)
        items.append({
            "id": t.id,
            "org_id": t.org_id,
            "org_name": getattr(t, "org_name", None),
            "org_code": getattr(t, "org_code", None),
            "service_id": t.service_id,
            "project_id": t.project_id,
            "service_name": getattr(t, "service_name", None),
            "service_type": getattr(t, "service_type", None),
            "service_status": getattr(t, "service_status", None),
            "subject": t.subject,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "ticket_type": t.ticket_type,
            "source": t.source,
            "raised_by": t.raised_by,
            "raised_by_email": t.raised_by_email,
            "assignee_id": t.assignee_id,
            "assignee_name": primary["full_name"] if primary else None,
            "assignee_email": primary["email"] if primary else None,
            "assignment_mode": t.assignment_mode,
            "assignees": assignees,
            "is_deleted": t.is_deleted,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            # Extra fields frontend may read
            "sla_state": t.sla_state,
            "response_by": t.response_by,
            "resolution_by": t.resolution_by,
            "team_id": t.team_id,
        })

    return {
        "items": items,
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
    replies_raw = replies_query.order_by(TicketReply.created_at.asc()).all()
    reply_author_ids = {r.author_id for r in replies_raw if r.author_id is not None}
    reply_authors = {u.id: u for u in db.query(User).filter(User.id.in_(reply_author_ids)).all()} if reply_author_ids else {}
    replies = [_resolve_reply_author(r, reply_authors) for r in replies_raw]

    # Fetch activities
    activities = (
        db.query(TicketActivity)
        .filter(TicketActivity.ticket_id == ticket_id)
        .order_by(TicketActivity.created_at.asc())
        .all()
    )

    # Lookup org/service/project/task names and assignees
    org = db.query(Organization).filter(Organization.id == ticket.org_id).first()
    svc = db.query(Service).filter(Service.id == ticket.service_id).first() if ticket.service_id else None
    project_name = None
    if ticket.project_id:
        from app.models.project import Project as _Project
        proj = db.query(_Project).filter(_Project.id == ticket.project_id).first()
        project_name = proj.name if proj else None
    task_title = None
    if ticket.task_id:
        from app.models.project import ProjectTask as _PTask
        ptask = db.query(_PTask).filter(_PTask.id == ticket.task_id).first()
        task_title = ptask.title if ptask else None

    assignees_map = load_assignees_for_tickets(db, [ticket.id])
    assignees = assignees_map.get(ticket.id, [])
    primary = next((a for a in assignees if a["is_primary"]), None)
    if primary:
        p_name, p_email = primary["full_name"], primary["email"]
    elif ticket.assignee_id:
        assignee = db.query(User).filter(User.id == ticket.assignee_id).first()
        p_name = assignee.full_name if assignee else None
        p_email = assignee.email if assignee else None
    else:
        p_name = p_email = None

    ticket_dict = {
        "id": ticket.id,
        "org_id": ticket.org_id,
        "org_name": org.name if org else None,
        "org_code": org.code if org else None,
        "service_id": ticket.service_id,
        "project_id": ticket.project_id,
        "project_name": project_name,
        "task_id": ticket.task_id,
        "task_title": task_title,
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
        "assignee_name": p_name,
        "assignee_email": p_email,
        "assignment_mode": ticket.assignment_mode,
        "assignees": assignees,
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
    background_tasks: BackgroundTasks,
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
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if new_status == "Waiting" and ticket.sla_paused_at is None:
            ticket.sla_paused_at = now_utc
        elif new_status == "In Progress" and ticket.sla_paused_at is not None:
            pause_duration = now_utc - ticket.sla_paused_at
            duration_seconds = int(pause_duration.total_seconds())
            if ticket.resolution_by:
                ticket.resolution_by = ticket.resolution_by + pause_duration
            if ticket.response_by:
                ticket.response_by = ticket.response_by + pause_duration
            ticket.sla_paused_total_seconds = (
                (ticket.sla_paused_total_seconds or 0) + duration_seconds
            )
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

    # Resolve assignee_ids: new multi-assignee or legacy single
    eff_ids: list[int] | None = None
    if "assignee_ids" in changes and changes["assignee_ids"] is not None:
        eff_ids = list(changes["assignee_ids"])
    elif "assignee_id" in changes and changes["assignee_id"] is not None:
        eff_ids = [changes["assignee_id"]]

    if eff_ids is not None:
        old_assignee = str(ticket.assignee_id) if ticket.assignee_id else None
        set_ticket_assignees(db, ticket, eff_ids, assigned_by=user.id)
        activity = TicketActivity(
            ticket_id=ticket.id,
            actor_id=user.id,
            action="assigned",
            from_value=old_assignee,
            to_value=str(ticket.assignee_id) if ticket.assignee_id else None,
        )
        db.add(activity)

    if "assignment_mode" in changes and changes["assignment_mode"] is not None:
        ticket.assignment_mode = changes["assignment_mode"]

    if "task_id" in changes and changes["task_id"] is not None:
        from app.models.project import ProjectTask as _PTask
        t_obj = db.query(_PTask).filter(_PTask.id == changes["task_id"]).first()
        if not t_obj:
            raise HTTPException(status_code=422, detail="Task not found")
        if ticket.project_id and t_obj.project_id != ticket.project_id:
            raise HTTPException(status_code=422, detail="Task does not belong to the ticket's project")
        ticket.task_id = changes["task_id"]
        if ticket.project_id is None:
            ticket.project_id = t_obj.project_id

    db.commit()
    db.refresh(ticket)

    # Email for significant status changes
    try:
        if "status" in changes and changes["status"] in ("Resolved", "Closed"):
            from app.services.email_sender import bg_send_email
            to_email = ticket.raised_by_email
            if to_email:
                new_status = changes["status"]
                ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket.id}"
                subject = f"[#{ticket.id}] Status changed to {new_status}"
                body_html = f"""<html><body style="font-family:Arial,sans-serif;color:#333">
<h2>Ticket #{ticket.id} — {new_status}</h2>
<p>Your ticket <strong>{ticket.subject}</strong> status: <strong>{new_status}</strong></p>
<p><a href="{ticket_url}">View Ticket</a></p></body></html>"""
                body_text = f"Ticket #{ticket.id} '{ticket.subject}' → {new_status}\n{ticket_url}"
                background_tasks.add_task(bg_send_email, to_email, subject, body_html, body_text)
    except Exception:
        pass

    # Socket.IO: notify affected users of ticket update
    try:
        from app.socketio_server import notify_user
        event_data = {"ticket_id": ticket.id, "status": ticket.status, "priority": ticket.priority, "assignee_id": ticket.assignee_id}  # noqa: E501
        notified = set()
        if ticket.raised_by:
            background_tasks.add_task(notify_user, ticket.raised_by, "ticket_updated", event_data)
            notified.add(ticket.raised_by)
        if ticket.assignee_id and ticket.assignee_id not in notified:
            background_tasks.add_task(notify_user, ticket.assignee_id, "ticket_updated", event_data)
    except Exception:
        pass

    return _ticket_out_dict(ticket, db)


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


# ── DELETE /api/tickets/{id}/permanent ───────────────────────────────────────

@router.delete("/{ticket_id}/permanent")
def hard_delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status not in ("Resolved", "Closed") and not ticket.is_deleted:
        raise HTTPException(
            status_code=400,
            detail="Only Resolved/Closed or already-deleted tickets can be permanently deleted",
        )

    # 1. Collect attachments and delete physical files before any DB changes
    attachments = db.query(TicketAttachment).filter(
        TicketAttachment.ticket_id == ticket_id
    ).all()
    attachment_ids = [a.id for a in attachments]
    freed = 0
    for att in attachments:
        if delete_attachment(att.file_path):
            freed += 1

    # 2. project_documents sourced from ticket_attachment → delete (SET NULL keeps upload-sourced ones)
    if attachment_ids:
        db.query(ProjectDocument).filter(
            ProjectDocument.ticket_attachment_id.in_(attachment_ids),
            ProjectDocument.source == "ticket_attachment",
        ).delete(synchronize_session=False)

    # 3. email_log and email_threads: no ondelete on their ticket_id FKs → must delete explicitly
    db.query(EmailLog).filter(EmailLog.ticket_id == ticket_id).delete(synchronize_session=False)
    db.query(EmailThread).filter(EmailThread.ticket_id == ticket_id).delete(synchronize_session=False)

    # 4. Delete ticket — DB CASCADE handles ticket_assignees, ticket_replies,
    #    ticket_activities, ticket_attachments, transfer_requests.
    #    project_documents.ticket_attachment_id remaining rows → SET NULL (FK defined).
    db.query(Ticket).filter(Ticket.id == ticket_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True, "ticket_id": ticket_id, "freed_attachments": freed}


# ── POST /api/tickets/{id}/replies ────────────────────────────────────────────

@router.post("/{ticket_id}/replies", status_code=201, response_model=TicketReplyOut)
def add_reply(
    ticket_id: int,
    payload: TicketReplyCreate,
    background_tasks: BackgroundTasks,
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
            pause_duration = datetime.now(timezone.utc).replace(tzinfo=None) - ticket.sla_paused_at
            duration_seconds = int(pause_duration.total_seconds())
            if ticket.resolution_by:
                ticket.resolution_by = ticket.resolution_by + pause_duration
            if ticket.response_by:
                ticket.response_by = ticket.response_by + pause_duration
            ticket.sla_paused_total_seconds = (
                (ticket.sla_paused_total_seconds or 0) + duration_seconds
            )
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
            from app.services.email_sender import bg_send_email
            ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket_id}"
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
                    background_tasks.add_task(bg_send_email, assignee.email, subject, body_html, body_text)
            elif user.role != "customer" and ticket.raised_by_email:
                background_tasks.add_task(bg_send_email, ticket.raised_by_email, subject, body_html, body_text)
    except Exception:
        pass

    # Socket.IO: push new reply to the other party with full data for realtime UI
    try:
        from app.socketio_server import notify_user
        event_data = {
            "ticket_id": ticket_id,
            "project_id": ticket.project_id,
            "reply_id": reply.id,
            "author_id": user.id,
            "author_name": user.full_name or user.email.split("@")[0],
            "author_role": user.role,
            "content": reply.content,
            "is_internal": reply.is_internal,
            "created_at": reply.created_at.isoformat() if reply.created_at else None,
            "ticket_subject": ticket.subject,
        }
        if user.role == "customer" and ticket.assignee_id:
            background_tasks.add_task(notify_user, ticket.assignee_id, "new_reply", event_data)
        elif user.role != "customer" and ticket.raised_by:
            background_tasks.add_task(notify_user, ticket.raised_by, "new_reply", event_data)
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
    set_ticket_assignees(db, ticket, [payload.assignee_id], assigned_by=user.id)
    ticket.assignment_mode = "manual"
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
    return _ticket_out_dict(ticket, db)


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
    replies = query.order_by(TicketReply.created_at.asc()).all()

    author_ids = {r.author_id for r in replies if r.author_id is not None}
    authors = {u.id: u for u in db.query(User).filter(User.id.in_(author_ids)).all()} if author_ids else {}
    return [_resolve_reply_author(r, authors) for r in replies]


# ── POST /api/tickets/{id}/attachments ────────────────────────────────────────

@router.post("/{ticket_id}/attachments", status_code=201, response_model=AttachmentOut)
@limiter.limit(config.RATE_LIMIT_FILE_UPLOAD)
async def upload_attachment(
    request: Request,
    ticket_id: int,
    file: UploadFile = File(...),
    reply_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)
    org_id = ticket.org_id

    file_data = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    original_name = file.filename or "upload"

    result = save_attachment(file_data, org_id, original_name, mime_type)

    attachment = TicketAttachment(
        ticket_id=ticket_id,
        reply_id=reply_id,
        file_name=original_name[:255],
        file_path=result["stored_path"],
        file_size=result["file_size"],
        mime_type=mime_type[:100],
        detected_mime=result["detected_mime"],
        sha256=result["sha256"],
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


# ── POST /api/tickets/{id}/create-project ─────────────────────────────────────

@router.post("/{ticket_id}/create-project", status_code=201)
def create_project_from_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)
    if ticket.project_id:
        raise HTTPException(status_code=409, detail="Ticket is already linked to a project")

    from app.models.project import Project as _Project, ProjectDocument
    from app.services.assignment import sync_project_members_from_ticket

    project = _Project(
        org_id=ticket.org_id,
        name=ticket.subject[:255],
        description=ticket.description,
        project_type="other",
        status="open",
        visibility="customer_visible",
        created_by=user.id,
    )
    db.add(project)
    db.flush()

    ticket.project_id = project.id

    sync_project_members_from_ticket(db, ticket, project.id, added_by_id=user.id)

    # Copy top-level ticket attachments (not reply attachments) as project doc references
    atts = (
        db.query(TicketAttachment)
        .filter(TicketAttachment.ticket_id == ticket_id, TicketAttachment.reply_id.is_(None))
        .all()
    )
    for att in atts:
        doc = ProjectDocument(
            project_id=project.id,
            file_name=att.file_name,
            file_path=att.file_path,
            file_size=att.file_size,
            mime_type=att.mime_type,
            detected_mime=att.detected_mime,
            sha256=att.sha256,
            is_client_visible=False,
            uploaded_by=user.id,
            ticket_attachment_id=att.id,
            source="ticket_attachment",
        )
        db.add(doc)

    db.add(TicketActivity(ticket_id=ticket_id, actor_id=user.id, action="project_created", to_value=str(project.id)))
    db.commit()
    db.refresh(project)

    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "org_id": project.org_id,
        "created_at": project.created_at,
    }


# ── POST /api/tickets/{id}/link-project ──────────────────────────────────────

@router.post("/{ticket_id}/link-project")
def link_project_to_ticket(
    ticket_id: int,
    payload: LinkProjectPayload,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)

    from app.models.project import Project as _Project
    from app.services.assignment import sync_project_members_from_ticket

    project = db.query(_Project).filter(_Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.org_id != ticket.org_id:
        raise HTTPException(status_code=404, detail="Project does not belong to the same organization")
    if ticket.project_id and ticket.project_id != payload.project_id:
        raise HTTPException(status_code=409, detail="Ticket is already linked to a different project")

    ticket.project_id = project.id
    sync_project_members_from_ticket(db, ticket, project.id, added_by_id=user.id)
    db.add(TicketActivity(ticket_id=ticket_id, actor_id=user.id, action="project_linked", to_value=str(project.id)))
    db.commit()

    return {"ticket_id": ticket_id, "project_id": project.id, "project_name": project.name}


# ── DELETE /api/tickets/{id}/unlink-project ───────────────────────────────────

@router.delete("/{ticket_id}/unlink-project")
def unlink_project_from_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    ticket = _get_ticket_in_scope(ticket_id, user, db)
    if not ticket.project_id:
        raise HTTPException(status_code=404, detail="Ticket is not linked to a project")

    old_project_id = ticket.project_id
    ticket.project_id = None
    db.add(TicketActivity(ticket_id=ticket_id, actor_id=user.id, action="project_unlinked", from_value=str(old_project_id)))
    db.commit()

    return {"message": "Project unlinked", "ticket_id": ticket_id}
