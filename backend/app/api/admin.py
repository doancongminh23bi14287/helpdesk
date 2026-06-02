# backend/app/api/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.database import get_db
from app.models.user import User
from app.models.sla import SlaPolicy
from app.core.deps import require_admin
from app.services.email_piping import process_inbox

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/email/poll")
def manual_email_poll(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    count = process_inbox(db)
    return {"processed": count}


class SlaPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    priority: str
    response_hours: float
    resolution_hours: float


class SlaPolicyUpdate(BaseModel):
    response_hours: Optional[float] = None
    resolution_hours: Optional[float] = None


_PRIORITY_ORDER = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}


@router.get("/sla/policies", response_model=List[SlaPolicyOut])
def list_sla_policies(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    policies = db.query(SlaPolicy).all()
    return sorted(policies, key=lambda p: _PRIORITY_ORDER.get(p.priority, 99))


@router.put("/sla/policies/{policy_id}", response_model=SlaPolicyOut)
def update_sla_policy(
    policy_id: int,
    payload: SlaPolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    policy = db.query(SlaPolicy).filter(SlaPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(policy, k, v)
    db.commit()
    db.refresh(policy)
    return policy
