from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.subscription import SubscriptionPlan
from app.models.item import Item
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.subscription import SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanOut

router = APIRouter(prefix="/api/subscription-plans", tags=["subscription-plans"])


def _enrich_plans(plans, db) -> List[SubscriptionPlanOut]:
    """Attach item unit_price to each plan (for frontend price previews)."""
    item_ids = list({p.item_id for p in plans if p.item_id})
    item_map = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}
    result = []
    for p in plans:
        item = item_map.get(p.item_id)
        out = SubscriptionPlanOut.model_validate(p)
        out.unit_price = Decimal(str(item.unit_price)) if item else None
        result.append(out)
    return result


@router.get("", response_model=List[SubscriptionPlanOut])
def list_subscription_plans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List subscription plans with item unit_price. Non-admins only see active plans."""
    if user.role == "admin":
        plans = db.query(SubscriptionPlan).all()
    else:
        plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).all()
    return _enrich_plans(plans, db)


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
    return _enrich_plans([plan], db)[0]


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
