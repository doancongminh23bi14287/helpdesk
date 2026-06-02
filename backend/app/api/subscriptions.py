from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from math import ceil
from app.database import get_db
from app.models.subscription import SubscriptionPlan, Subscription
from app.models.organization import Organization
from app.models.user import User
from app.models.team import StaffOrgAssignment
from app.core.deps import get_current_user, require_admin
from app.schemas.subscription import SubscriptionCreate, SubscriptionOut
from app.services.billing import create_subscription, cancel_subscription

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

VALID_SUB_SORT_FIELDS = {"start_date", "next_billing_date", "status", "created_at"}


def _build_subscriptions_out(subs, db):
    """Batch-fetch plans and orgs to avoid N+1 queries."""
    plan_ids = list({s.subscription_plan_id for s in subs})
    org_ids = list({s.org_id for s in subs})
    plan_map = {p.id: p for p in db.query(SubscriptionPlan).filter(SubscriptionPlan.id.in_(plan_ids)).all()} if plan_ids else {}
    org_map = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}

    result = []
    for s in subs:
        plan = plan_map.get(s.subscription_plan_id)
        org = org_map.get(s.org_id)
        result.append(SubscriptionOut(
            **{c.key: getattr(s, c.key) for c in s.__table__.columns},
            plan_name=plan.name if plan else None,
            org_name=org.name if org else None,
        ))
    return result


def _enrich_one(sub, db):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.subscription_plan_id).first()
    org = db.query(Organization).filter(Organization.id == sub.org_id).first()
    return SubscriptionOut(
        **{c.key: getattr(sub, c.key) for c in sub.__table__.columns},
        plan_name=plan.name if plan else None,
        org_name=org.name if org else None,
    )


def _get_accessible_org_ids(user: User, db: Session) -> Optional[List[int]]:
    """Returns None for admin (all), list of org IDs for staff/customer."""
    if user.role == "admin":
        return None
    if user.role == "customer":
        return [user.org_id]
    # staff
    rows = db.query(StaffOrgAssignment).filter(StaffOrgAssignment.user_id == user.id).all()
    return [r.org_id for r in rows]


@router.get("/my", response_model=List[SubscriptionOut])
def get_my_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Customer sees only their org's subscriptions."""
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customers only")
    subs = db.query(Subscription).filter(Subscription.org_id == user.org_id).all()
    return _build_subscriptions_out(subs, db)


@router.get("")
def list_subscriptions(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List subscriptions scoped by role."""
    from sqlalchemy import or_
    org_ids = _get_accessible_org_ids(user, db)
    q = db.query(Subscription)
    if org_ids is not None:
        q = q.filter(Subscription.org_id.in_(org_ids))
    if status:
        q = q.filter(Subscription.status == status)
    # Search: match on org name via join
    if search:
        term = f"%{search}%"
        q = q.join(Organization, Subscription.org_id == Organization.id).filter(
            Organization.name.ilike(term)
        )
    # Sort
    if sort not in VALID_SUB_SORT_FIELDS:
        sort = "created_at"
    sort_col = getattr(Subscription, sort, Subscription.created_at)
    q = q.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    total = q.count()
    subs = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": _build_subscriptions_out(subs, db),
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


@router.post("", response_model=SubscriptionOut, status_code=201)
def create_subscription_endpoint(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a new subscription (admin only)."""
    try:
        sub = create_subscription(
            db=db,
            org_id=payload.org_id,
            plan_id=payload.plan_id,
            start_date=payload.start_date,
            price_list_id=payload.price_list_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_one(sub, db)


@router.get("/{sub_id}", response_model=SubscriptionOut)
def get_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single subscription scoped by role."""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    org_ids = _get_accessible_org_ids(user, db)
    if org_ids is not None and sub.org_id not in org_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    return _enrich_one(sub, db)


@router.put("/{sub_id}/cancel", response_model=SubscriptionOut)
def cancel_subscription_endpoint(
    sub_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Cancel a subscription (admin only)."""
    try:
        sub = cancel_subscription(db=db, subscription_id=sub_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_one(sub, db)
