from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.team import StaffOrgAssignment
from app.models.user import User
from app.models.organization import Organization
from app.core.deps import require_admin

router = APIRouter(prefix="/api/staff-assignments", tags=["staff-assignments"])


class AssignmentIn(BaseModel):
    user_id: int
    org_id: int


class AssignmentOut(BaseModel):
    user_id: int
    org_id: int
    user_email: str
    user_name: str
    org_name: str
    org_code: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[AssignmentOut])
def list_assignments(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = db.query(StaffOrgAssignment).all()
    if not rows:
        return []
    user_ids = [r.user_id for r in rows]
    org_ids = [r.org_id for r in rows]
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
    org_map = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()}
    result = []
    for row in rows:
        user = user_map.get(row.user_id)
        org = org_map.get(row.org_id)
        if user and org:
            result.append(AssignmentOut(
                user_id=row.user_id,
                org_id=row.org_id,
                user_email=user.email,
                user_name=user.full_name,
                org_name=org.name,
                org_code=org.code,
            ))
    return result


@router.post("", status_code=201)
def create_assignment(
    payload: AssignmentIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == payload.user_id, User.role == "staff").first()
    if not user:
        raise HTTPException(status_code=404, detail="Staff user not found")
    org = db.query(Organization).filter(Organization.id == payload.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    existing = db.query(StaffOrgAssignment).filter(
        StaffOrgAssignment.user_id == payload.user_id,
        StaffOrgAssignment.org_id == payload.org_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Assignment already exists")
    db.add(StaffOrgAssignment(user_id=payload.user_id, org_id=payload.org_id))
    db.commit()
    return {"user_id": payload.user_id, "org_id": payload.org_id}


@router.delete("", status_code=204)
def delete_assignment(
    user_id: int,
    org_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    row = db.query(StaffOrgAssignment).filter(
        StaffOrgAssignment.user_id == user_id,
        StaffOrgAssignment.org_id == org_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(row)
    db.commit()
