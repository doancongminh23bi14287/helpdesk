# backend/app/api/services.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.service import Service
from app.models.team import StaffOrgAssignment
from app.models.user import User
from app.core.deps import get_current_user
from app.schemas.organization import ServiceOut

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=List[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return services scoped to the user's role."""
    query = db.query(Service)

    if user.role == "admin":
        pass  # no restriction
    elif user.role == "staff":
        assigned_orgs = (
            select(StaffOrgAssignment.org_id)
            .where(StaffOrgAssignment.user_id == user.id)
            .scalar_subquery()
        )
        query = query.filter(Service.org_id.in_(assigned_orgs))
    else:  # customer
        query = query.filter(Service.org_id == user.org_id)

    return query.order_by(Service.name.asc()).all()
