"""Deprecated permission helpers.

New code should use app.core.scoping. These helpers are kept temporarily for
backward compatibility with any out-of-tree imports while the codebase
standardizes on centralized scoping.
"""

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.team import StaffOrgAssignment


def org_scope_filter(query, model_class, user: User):
    """Apply org-based row-level filter to a SQLAlchemy query.
    Call at the top of every list endpoint.
    """
    if user.role == "admin":
        return query
    if user.role == "staff":
        assigned = (
            select(StaffOrgAssignment.org_id)
            .where(StaffOrgAssignment.user_id == user.id)
            .scalar_subquery()
        )
        return query.filter(model_class.org_id.in_(assigned))
    # customer — own org only
    return query.filter(model_class.org_id == user.org_id)


def get_ticket_scope_filter(user: User, db: Session):
    """Return a SQLAlchemy filter clause for ticket visibility, or None for admin.

    Staff: tickets in assigned orgs OR directly assigned to them.
    Customer: only their own tickets in their own org.
    """
    from app.models.ticket import Ticket

    if user.role == "admin":
        return None

    if user.role == "staff":
        assigned_subq = (
            select(StaffOrgAssignment.org_id)
            .where(StaffOrgAssignment.user_id == user.id)
            .scalar_subquery()
        )
        return or_(
            Ticket.org_id.in_(assigned_subq),
            Ticket.assignee_id == user.id,
        )

    # customer: only tickets they raised in their own org
    return and_(
        Ticket.raised_by == user.id,
        Ticket.org_id == user.org_id,
    )
