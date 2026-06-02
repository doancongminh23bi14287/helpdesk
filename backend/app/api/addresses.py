from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.address import Address
from app.models.organization import Organization
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.address import AddressCreate, AddressUpdate, AddressOut

router = APIRouter(prefix="/api/organizations", tags=["addresses"])


def _get_org_or_404(org_id: int, db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _check_access(org_id: int, user: User, db: Session):
    if user.role == "customer" and user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if user.role == "staff":
        from app.models.team import StaffOrgAssignment
        assigned = db.query(StaffOrgAssignment).filter(
            StaffOrgAssignment.user_id == user.id,
            StaffOrgAssignment.org_id == org_id,
        ).first()
        if not assigned:
            raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{org_id}/addresses", response_model=List[AddressOut])
def list_addresses(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_org_or_404(org_id, db)
    _check_access(org_id, user, db)
    return db.query(Address).filter(Address.org_id == org_id).all()


@router.post("/{org_id}/addresses", response_model=AddressOut)
def create_address(
    org_id: int,
    payload: AddressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    _get_org_or_404(org_id, db)
    address = Address(org_id=org_id, **payload.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.put("/{org_id}/addresses/{address_id}", response_model=AddressOut)
def update_address(
    org_id: int,
    address_id: int,
    payload: AddressUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    address = db.query(Address).filter(
        Address.id == address_id, Address.org_id == org_id
    ).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(address, k, v)
    db.commit()
    db.refresh(address)
    return address


@router.delete("/{org_id}/addresses/{address_id}", status_code=204)
def delete_address(
    org_id: int,
    address_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    address = db.query(Address).filter(
        Address.id == address_id, Address.org_id == org_id
    ).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    db.delete(address)
    db.commit()
