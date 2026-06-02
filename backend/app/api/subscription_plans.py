from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.subscription import SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanOut

router = APIRouter(prefix="/api/subscription-plans", tags=["subscription-plans"])


@router.get("", response_model=List[SubscriptionPlanOut])
def list_subscription_plans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List subscription plans. Non-admins only see active plans."""
    if user.role == "admin":
        return db.query(SubscriptionPlan).all()
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).all()


@router.post("", response_model=SubscriptionPlanOut)
def create_subscription_plan(
    payload: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a new subscription plan (admin only)."""
    if db.query(SubscriptionPlan).filter(SubscriptionPlan.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Subscription plan code already exists")
    plan = SubscriptionPlan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/{plan_id}", response_model=SubscriptionPlanOut)
def get_subscription_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single subscription plan (all roles)."""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    return plan


@router.put("/{plan_id}", response_model=SubscriptionPlanOut)
def update_subscription_plan(
    plan_id: int,
    payload: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update a subscription plan (admin only)."""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan
