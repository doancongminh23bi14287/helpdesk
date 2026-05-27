# backend/app/api/organizations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.organization import Organization
from app.models.service import Service
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.core.permissions import org_scope_filter
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationOut, ServiceOut

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.get("", response_model=List[OrganizationOut])
def list_organizations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Organization)
    if user.role == "admin":
        return query.all()
    if user.role == "customer":
        return query.filter(Organization.id == user.org_id).all()
    # staff — use org_scope_filter via staff_org_assignments subquery
    from sqlalchemy import select
    from app.models.team import StaffOrgAssignment
    assigned = (
        select(StaffOrgAssignment.org_id)
        .where(StaffOrgAssignment.user_id == user.id)
        .scalar_subquery()
    )
    return query.filter(Organization.id.in_(assigned)).all()


@router.post("", response_model=OrganizationOut)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if db.query(Organization).filter(Organization.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Organization code already exists")
    org = Organization(**payload.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrganizationOut)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role == "customer" and org.id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return org


@router.put("/{org_id}", response_model=OrganizationOut)
def update_organization(
    org_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(org, k, v)
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}/services", response_model=List[ServiceOut])
def get_org_services(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "customer" and org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.query(Service).filter(Service.org_id == org_id).all()
