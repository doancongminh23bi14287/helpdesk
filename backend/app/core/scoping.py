# backend/app/core/scoping.py
"""
Centralized org-level data-isolation helpers.

Every router that needs role-based row filtering should import from here
instead of writing its own inline logic.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.ticket import Ticket
from app.models.invoice import Invoice
from app.models.subscription import Subscription
from app.models.service import Service
from app.models.notification import Notification
from app.models.project import Project, ProjectTask


# ── org-id resolution ─────────────────────────────────────────────────────────

def get_accessible_org_ids(user: User, db: Session) -> Optional[List[int]]:
    """
    Return the org_ids visible to the user.

    - Admin  → None   (caller must not filter — sees everything)
    - Staff  → list of org_ids from staff_org_assignments
    - Customer → [user.org_id]
    """
    if user.role == "admin":
        return None
    if user.role == "staff":
        from app.models.team import StaffOrgAssignment
        rows = (
            db.query(StaffOrgAssignment.org_id)
            .filter(StaffOrgAssignment.user_id == user.id)
            .all()
        )
        return [r.org_id for r in rows]
    # customer
    return [user.org_id]


# ── generic helper ────────────────────────────────────────────────────────────

def scope_query(query, model, user: User, db: Session):
    """
    Apply org_id row-level filtering to any query whose model has an org_id column.
    Admin queries are returned unchanged.
    """
    org_ids = get_accessible_org_ids(user, db)
    if org_ids is None:
        return query
    return query.filter(model.org_id.in_(org_ids))


# ── per-resource scoping ──────────────────────────────────────────────────────

def scope_tickets(query, user: User, db: Session):
    """
    Apply ticket visibility rules:
      - Admin   : unrestricted
      - Customer: own tickets in own org only
      - Staff   : tickets in assigned orgs OR tickets personally assigned to them
    """
    if user.role == "admin":
        return query
    if user.role == "customer":
        return query.filter(
            Ticket.raised_by == user.id,
            Ticket.org_id == user.org_id,
        )
    # staff: direct assignment never expands tenant access.
    org_ids = get_accessible_org_ids(user, db)
    return query.filter(Ticket.org_id.in_(org_ids or []))


def scope_invoices(query, user: User, db: Session):
    return scope_query(query, Invoice, user, db)


def scope_subscriptions(query, user: User, db: Session):
    return scope_query(query, Subscription, user, db)


def scope_services(query, user: User, db: Session):
    return scope_query(query, Service, user, db)


def scope_notifications(query, user: User, db: Session):
    """Notifications are user-scoped, not org-scoped."""
    return query.filter(Notification.user_id == user.id)


def scope_projects(query, user: User, db: Session, include_internal: bool = False):
    """
    Apply SEO project visibility rules.

    - Admin: unrestricted
    - Staff: projects in assigned orgs OR projects where staff has an assigned ticket
    - Customer: own org and customer-visible projects only
    """
    if user.role == "admin":
        return query
    if user.role == "customer":
        return query.filter(
            Project.org_id == user.org_id,
            Project.visibility == "customer_visible",
        )
    # staff: ticket assignment never expands organisation access.
    org_ids = get_accessible_org_ids(user, db)
    return query.filter(Project.org_id.in_(org_ids or []))


def scope_project_tasks(query, user: User, db: Session, include_internal: bool = False):
    """
    Apply SEO project task visibility rules.

    Callers may pass either a ProjectTask query already joined to Project or a
    plain ProjectTask query; this helper joins Project when needed.
    """
    query = query.join(Project, Project.id == ProjectTask.project_id)
    if user.role == "admin":
        return query
    if user.role == "customer":
        return query.filter(
            Project.org_id == user.org_id,
            Project.visibility == "customer_visible",
            ProjectTask.is_client_visible == True,  # noqa: E712
        )
    org_ids = get_accessible_org_ids(user, db)
    return query.filter(Project.org_id.in_(org_ids or []))


def get_ticket_in_scope(ticket_id: int, user: User, db: Session) -> Ticket:
    """Return a visible non-deleted ticket or raise 404 for missing/out-of-scope."""
    from fastapi import HTTPException

    ticket = scope_tickets(
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False),
        user,
        db,
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def assert_project_access(project_id: int, user: User, db: Session) -> Project:
    """Return a visible project or raise 404 for missing/out-of-scope."""
    from fastapi import HTTPException

    project = scope_projects(
        db.query(Project).filter(Project.id == project_id),
        user,
        db,
        include_internal=user.role in {"admin", "staff"},
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def assert_project_task_access(task_id: int, user: User, db: Session) -> ProjectTask:
    """Return a visible project task or raise 404 for missing/out-of-scope."""
    from fastapi import HTTPException

    task = scope_project_tasks(
        db.query(ProjectTask).filter(ProjectTask.id == task_id),
        user,
        db,
        include_internal=user.role in {"admin", "staff"},
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Project task not found")
    return task


# ── single-resource access guard ─────────────────────────────────────────────

def assert_org_access(resource_org_id: int, user: User, db: Session) -> None:
    """
    Raise HTTPException 404 if the user cannot access resource_org_id.
    No-op for admins.
    """
    from fastapi import HTTPException

    org_ids = get_accessible_org_ids(user, db)
    if org_ids is not None and resource_org_id not in org_ids:
        raise HTTPException(status_code=404, detail="Resource not found")
