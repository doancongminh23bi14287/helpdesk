"""
Keeps the Service row linked to a Subscription in sync with the subscription's
billing fields.  Called from billing.py (create) and api/subscriptions.py (cancel).

# Call sync_service_from_subscription() here if a future endpoint updates
# subscription fields (unit_price, billing_cycle, etc.).
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.service import Service
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.item import Item

_STATUS_MAP = {
    "trial":     "active",
    "active":    "active",
    "past_due":  "past_due",
    "cancelled": "cancelled",
    "expired":   "inactive",
}

_VALID_SERVICE_TYPES = {"saas", "hosting", "domain", "support", "other"}


def sync_service_from_subscription(
    db: Session,
    subscription: Subscription,
    create_if_missing: bool = True,
) -> "Service | None":
    """
    Find the Service linked to `subscription` (via subscription_id) and sync:
      name, type, status, monthly_cost, billing_cycle, expiry_date.

    Creates a new Service if none exists and create_if_missing is True.
    Returns the Service, or None when not found and create_if_missing is False.
    """
    item = (
        db.query(Item).filter(Item.id == subscription.item_id).first()
        if subscription.item_id else None
    )
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.id == subscription.subscription_plan_id)
        .first()
        if subscription.subscription_plan_id else None
    )

    name = (
        (item.name if item else None)
        or (plan.name if plan else f"Subscription #{subscription.id}")
    )
    svc_type = (
        item.type if item and item.type in _VALID_SERVICE_TYPES else "other"
    )
    svc_status = _STATUS_MAP.get(subscription.status, "active")
    monthly_cost = float(subscription.unit_price) if subscription.unit_price is not None else None
    expiry_date = subscription.current_period_end

    svc = (
        db.query(Service)
        .filter(Service.subscription_id == subscription.id)
        .with_for_update()
        .first()
    )

    if svc is None:
        if not create_if_missing:
            return None
        svc = Service(
            org_id=subscription.org_id,
            name=name,
            type=svc_type,
            status=svc_status,
            monthly_cost=monthly_cost,
            billing_cycle=subscription.billing_cycle,
            start_date=subscription.start_date,
            expiry_date=expiry_date,
            subscription_id=subscription.id,
            category_id=None,
            domain=None,
            disk_usage=None,
        )
        db.add(svc)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            svc = db.query(Service).filter(Service.subscription_id == subscription.id).first()
            if svc is None:
                raise
    else:
        svc.name = name
        svc.type = svc_type
        svc.status = svc_status
        svc.monthly_cost = monthly_cost
        svc.billing_cycle = subscription.billing_cycle
        svc.expiry_date = expiry_date

    db.commit()
    db.refresh(svc)
    return svc
