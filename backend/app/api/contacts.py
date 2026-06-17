from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact import Contact
from app.models.organization import Organization
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.contact import ContactCreate, ContactUpdate, ContactOut


def _contact_to_out(c: Contact) -> ContactOut:
    u = c.user
    return ContactOut(
        id=c.id, org_id=c.org_id, user_id=c.user_id,
        name=c.name, email=c.email, phone=c.phone,
        role=c.role, is_active=c.is_active, created_at=c.created_at,
        user_email=u.email if u else None,
        user_full_name=u.full_name if u else None,
        is_portal_user=u is not None,
    )


class LinkUserPayload(BaseModel):
    user_id: Optional[int] = None

router = APIRouter(prefix="/api/organizations", tags=["contacts"])


def _get_org_or_404(org_id: int, db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _check_access(org_id: int, user: User, db: Session):
    if user.role == "customer" and user.org_id != org_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role == "staff":
        from app.models.team import StaffOrgAssignment
        assigned = db.query(StaffOrgAssignment).filter(
            StaffOrgAssignment.user_id == user.id,
            StaffOrgAssignment.org_id == org_id,
        ).first()
        if not assigned:
            raise HTTPException(status_code=404, detail="Organization not found")


@router.get("/{org_id}/contacts", response_model=List[ContactOut])
def list_contacts(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_org_or_404(org_id, db)
    _check_access(org_id, user, db)
    contacts = db.query(Contact).filter(Contact.org_id == org_id).all()
    return [_contact_to_out(c) for c in contacts]


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
    return _contact_to_out(contact)


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
    return _contact_to_out(contact)


@router.put("/{org_id}/contacts/{contact_id}/link-user", response_model=ContactOut)
def link_user_to_contact(
    org_id: int,
    contact_id: int,
    payload: LinkUserPayload,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id, Contact.org_id == org_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if payload.user_id is not None:
        target_user = db.query(User).filter(User.id == payload.user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        # Only enforce org check for customer users. Staff and admins belong to
        # the provider org, so their org_id will never match the client org_id —
        # blocking them here would prevent legitimate staff→contact links.
        if target_user.role == "customer" and target_user.org_id != org_id:
            raise HTTPException(status_code=400, detail="User does not belong to this organization")
        # Unlink this user_id from any other contact first
        db.query(Contact).filter(
            Contact.user_id == payload.user_id,
            Contact.id != contact_id,
        ).update({"user_id": None})
    contact.user_id = payload.user_id
    db.commit()
    db.refresh(contact)
    return _contact_to_out(contact)


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
