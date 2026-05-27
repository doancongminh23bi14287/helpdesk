# backend/app/core/permissions.py
from sqlalchemy import select
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
