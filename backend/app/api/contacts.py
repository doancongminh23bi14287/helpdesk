from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.contact import Contact
from app.models.organization import Organization
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.contact import ContactCreate, ContactUpdate, ContactOut

router = APIRouter(prefix="/api/organizations", tags=["contacts"])


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


@router.get("/{org_id}/contacts", response_model=List[ContactOut])
def list_contacts(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_org_or_404(org_id, db)
    _check_access(org_id, user, db)
    return db.query(Contact).filter(Contact.org_id == org_id).all()


@router.post("/{org_id}/contacts", response_model=ContactOut)
def create_contact(
    org_id: int,
    payload: ContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    _get_org_or_404(org_id, db)
    contact = Contact(org_id=org_id, **payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.put("/{org_id}/contacts/{contact_id}", response_model=ContactOut)
def update_contact(
    org_id: int,
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id, Contact.org_id == org_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(contact, k, v)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{org_id}/contacts/{contact_id}", status_code=204)
def delete_contact(
    org_id: int,
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id, Contact.org_id == org_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
