# backend/app/api/organizations.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from math import ceil
from app.database import get_db
from app.models.organization import Organization
from app.models.service import Service
from app.models.contact import Contact
from app.models.address import Address
from app.models.item import PriceList
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationOut,
    PriceListAssign, ServiceOut,
)

router = APIRouter(prefix="/api/organizations", tags=["organizations"])

VALID_ORG_SORT_FIELDS = {"name", "code", "contact_email", "status", "created_at"}


def _enrich_org(org: Organization, db: Session) -> OrganizationOut:
    """Build OrganizationOut with computed extra fields."""
    contacts_count = db.query(Contact).filter(Contact.org_id == org.id).count()
    addresses_count = db.query(Address).filter(Address.org_id == org.id).count()
    price_list_name = None
    if org.price_list_id:
        pl = db.query(PriceList).filter(PriceList.id == org.price_list_id).first()
        if pl:
            price_list_name = pl.name
    return OrganizationOut(
        id=org.id,
        name=org.name,
        code=org.code,
        contact_email=org.contact_email,
        phone=org.phone,
        status=org.status,
        notes=org.notes,
        created_at=org.created_at,
        price_list_id=org.price_list_id,
        price_list_name=price_list_name,
        contacts_count=contacts_count,
        addresses_count=addresses_count,
    )


@router.get("")
def list_organizations(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=500),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Organization)
    # Role-based scoping
    if user.role == "customer":
        query = query.filter(Organization.id == user.org_id)
    elif user.role == "staff":
        from sqlalchemy import select
        from app.models.team import StaffOrgAssignment
        assigned = (
            select(StaffOrgAssignment.org_id)
            .where(StaffOrgAssignment.user_id == user.id)
            .scalar_subquery()
        )
        query = query.filter(Organization.id.in_(assigned))
    # Search filter
    if search:
        term = f"%{search}%"
        query = query.filter(or_(
            Organization.name.ilike(term),
            Organization.code.ilike(term),
            Organization.contact_email.ilike(term),
        ))
    # Sort
    if sort not in VALID_ORG_SORT_FIELDS:
        sort = "created_at"
    sort_col = getattr(Organization, sort, Organization.created_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    total = query.count()
    orgs = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [_enrich_org(o, db) for o in orgs],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


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
    return _enrich_org(org, db)


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
    return _enrich_org(org, db)


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
    return _enrich_org(org, db)


@router.put("/{org_id}/price-list", response_model=OrganizationOut)
def assign_price_list(
    org_id: int,
    payload: PriceListAssign,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if payload.price_list_id is not None:
        pl = db.query(PriceList).filter(PriceList.id == payload.price_list_id, PriceList.is_active.is_(True)).first()
        if not pl:
            raise HTTPException(status_code=404, detail="Price list not found or inactive")
    org.price_list_id = payload.price_list_id
    db.commit()
    db.refresh(org)
    return _enrich_org(org, db)


@router.get("/{org_id}/services", response_model=List[ServiceOut])
def get_org_services(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role == "customer" and org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.query(Service).filter(Service.org_id == org_id).all()
