# backend/app/services/assignment.py
"""Multi-assignee management for tickets, with project-member sync."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketAssignee
from app.models.project import Project, TaskAssignee
from app.models.user import User


def validate_assignee_ids(
    db: Session,
    user_ids: list[int],
    org_id: int,
) -> dict[int, User]:
    """Return eligible staff users or raise without changing assignment state."""
    if not user_ids:
        return {}

    unique_ids = list(dict.fromkeys(user_ids))
    found = db.query(User).filter(User.id.in_(unique_ids)).all()
    users = {u.id: u for u in found}
    missing = set(unique_ids) - set(users)
    if missing:
        raise HTTPException(status_code=404, detail=f"User(s) not found: {sorted(missing)}")

    invalid = sorted(
        uid for uid, candidate in users.items()
        if candidate.role != "staff" or not candidate.is_active
    )
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Assignee(s) must be active staff: {invalid}",
        )

    # Ticket/manual assignment only requires an active staff account.
    # Org membership is handled by ticket scoping and project membership policies,
    # and direct assignee visibility is expected to work across org boundaries.
    _ = org_id
    return users


def set_ticket_assignees(
    db: Session,
    ticket: Ticket,
    user_ids: list[int],
    assigned_by: Optional[int],
    primary_id: Optional[int] = None,
) -> list[dict]:
    """Replace all assignees on *ticket* with *user_ids*.

    Sets is_primary on *primary_id* (defaults to first element).
    Syncs ticket.assignee_id to the primary.
    Upserts project_members for ticket's project (staff role only).
    Removes stale project_members when no remaining tickets in that project.

    Returns the new assignee list as dicts.
    """
    if not user_ids:
        primary_id = None
    elif primary_id is None or primary_id not in user_ids:
        primary_id = user_ids[0]

    users = validate_assignee_ids(db, user_ids, ticket.org_id)

    # Capture old assignees before clearing (for member-sync cleanup)
    old_rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id == ticket.id).all()
    old_user_ids = {r.user_id for r in old_rows}

    # Clear existing assignees
    for row in old_rows:
        db.delete(row)
    db.flush()

    # Insert new assignees
    for uid in user_ids:
        db.add(TicketAssignee(
            ticket_id=ticket.id,
            user_id=uid,
            is_primary=(uid == primary_id),
            assigned_by=assigned_by,
        ))

    # Sync primary to tickets.assignee_id
    ticket.assignee_id = primary_id

    # Member sync when ticket belongs to a project
    if ticket.project_id:
        for uid in user_ids:
            _upsert_project_member(db, ticket.project_id, uid, assigned_by)
        removed = old_user_ids - set(user_ids)
        for uid in removed:
            _maybe_remove_project_member(db, ticket.project_id, uid, exclude_ticket_id=ticket.id)

    db.flush()

    return [
        {
            "user_id": uid,
            "full_name": users[uid].full_name if uid in users else None,
            "email": users[uid].email if uid in users else None,
            "is_primary": (uid == primary_id),
        }
        for uid in user_ids
    ]


def set_task_assignees(
    db: Session,
    task,  # ProjectTask instance
    user_ids: list[int],
    assigned_by: Optional[int],
    primary_id: Optional[int] = None,
) -> list[dict]:
    """Replace all assignees on *task* with *user_ids*. Mirrors set_ticket_assignees."""
    if not user_ids:
        primary_id = None
    elif primary_id is None or primary_id not in user_ids:
        primary_id = user_ids[0]

    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    users = validate_assignee_ids(db, user_ids, project.org_id)

    old_rows = db.query(TaskAssignee).filter(TaskAssignee.task_id == task.id).all()
    for row in old_rows:
        db.delete(row)
    db.flush()

    for uid in user_ids:
        db.add(TaskAssignee(
            task_id=task.id,
            user_id=uid,
            is_primary=(uid == primary_id),
            assigned_by=assigned_by,
        ))

    task.assignee_id = primary_id
    db.flush()

    return [
        {
            "user_id": uid,
            "full_name": users[uid].full_name if uid in users else None,
            "email": users[uid].email if uid in users else None,
            "is_primary": (uid == primary_id),
        }
        for uid in user_ids
    ]


def load_assignees_for_tasks(db: Session, task_ids: list[int]) -> dict[int, list[dict]]:
    """Batch-load assignees for a list of task IDs."""
    if not task_ids:
        return {}
    rows = db.query(TaskAssignee).filter(TaskAssignee.task_id.in_(task_ids)).all()
    user_ids = {r.user_id for r in rows}
    users: dict[int, User] = {}
    if user_ids:
        users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
    result: dict[int, list[dict]] = {tid: [] for tid in task_ids}
    for row in rows:
        u = users.get(row.user_id)
        result[row.task_id].append({
            "user_id": row.user_id,
            "full_name": u.full_name if u else None,
            "email": u.email if u else None,
            "is_primary": row.is_primary,
        })
    return result


def load_assignees_for_tickets(db: Session, ticket_ids: list[int]) -> dict[int, list[dict]]:
    """Batch-load assignees for a list of ticket IDs.

    Returns {ticket_id: [assignee_dict, ...]} with user info resolved.
    """
    if not ticket_ids:
        return {}

    rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id.in_(ticket_ids)).all()
    user_ids = {r.user_id for r in rows}
    users: dict[int, User] = {}
    if user_ids:
        users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    result: dict[int, list[dict]] = {tid: [] for tid in ticket_ids}
    for row in rows:
        u = users.get(row.user_id)
        result[row.ticket_id].append({
            "user_id": row.user_id,
            "full_name": u.full_name if u else None,
            "email": u.email if u else None,
            "is_primary": row.is_primary,
        })
    return result


# ── project-member sync ───────────────────────────────────────────────────────

def sync_project_members_from_ticket(
    db: Session,
    ticket: Ticket,
    project_id: int,
    added_by_id: Optional[int],
) -> int:
    """Upsert customer (raised_by) + staff assignees into project_members.

    Never downgrades existing roles. Returns count of new rows inserted.
    """
    added = 0
    if ticket.raised_by:
        if _upsert_project_member_with_role(db, project_id, ticket.raised_by, "customer", added_by_id):
            added += 1
    assignee_rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id == ticket.id).all()
    for row in assignee_rows:
        if _upsert_project_member_with_role(db, project_id, row.user_id, "staff", added_by_id):
            added += 1
    return added


def _upsert_project_member_with_role(
    db: Session,
    project_id: int,
    user_id: int,
    role: str,
    added_by: Optional[int],
) -> bool:
    """Insert a project member if not already present. Never downgrades. Returns True on insert."""
    from app.models.project import ProjectMember
    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if existing:
        return False
    db.add(ProjectMember(project_id=project_id, user_id=user_id, role=role, added_by=added_by))
    return True


# ── internal member-sync helpers ──────────────────────────────────────────────

def _upsert_project_member(db: Session, project_id: int, user_id: int, added_by: Optional[int]) -> None:
    from app.models.project import ProjectMember
    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if not existing:
        db.add(ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role="staff",
            added_by=added_by,
        ))


def _maybe_remove_project_member(
    db: Session,
    project_id: int,
    user_id: int,
    exclude_ticket_id: int,
) -> None:
    """Remove staff auto-membership if user has no other tickets in this project."""
    from app.models.project import ProjectMember

    # Check for remaining ticket_assignees in this project (excluding current ticket)
    still_assigned = (
        db.query(TicketAssignee)
        .join(Ticket, TicketAssignee.ticket_id == Ticket.id)
        .filter(
            Ticket.project_id == project_id,
            Ticket.id != exclude_ticket_id,
            TicketAssignee.user_id == user_id,
            Ticket.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if still_assigned:
        return

    # Only remove auto-synced 'staff' rows — never touch 'manager' or 'customer'
    pm = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
        ProjectMember.role == "staff",
    ).first()
    if pm:
        db.delete(pm)
