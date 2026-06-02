from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.subscription import SubscriptionPlan, Subscription
from app.models.item import Item, PriceList, PriceListItem
from app.models.organization import Organization


def compute_next_billing_date(current_period_end: date) -> date:
    """
    Next billing date is the day AFTER current_period_end.
    """
    return current_period_end + timedelta(days=1)


def _add_period(start: date, months: int = 0, years: int = 0) -> date:
    """
    Add a period to a start date and return the last day of the resulting period.

    Logic:
    - Compute next_dt = start + relativedelta(months=months, years=years).
    - relativedelta clamps month-end dates (e.g. Jan 31 + 1 month = Feb 29 in a leap year).
    - If clamping occurred (next_dt.day != start.day), next_dt is already the last day
      of the target month — return it as the period end.
    - Otherwise subtract one day so that a period starting Jan 1 ends Jan 31, not Feb 1.
    """
    next_dt = start + relativedelta(months=months, years=years)
    if next_dt.day != start.day:
        # Month-end clamping: next_dt is already the last valid day of that month.
        return next_dt
    return next_dt - timedelta(days=1)


def compute_period_end(start: date, billing_cycle: str) -> date:
    """
    Compute period end date based on billing cycle.
    - monthly:   start + 1 month  (e.g., Jan 1 → Jan 31, Jan 31 → Feb 28/29)
    - quarterly: start + 3 months (e.g., Jan 1 → Mar 31)
    - yearly:    start + 1 year   (e.g., Jan 1 → Dec 31)

    Uses dateutil.relativedelta for correct month-end arithmetic.
    """
    if billing_cycle == "monthly":
        return _add_period(start, months=1)
    elif billing_cycle == "quarterly":
        return _add_period(start, months=3)
    elif billing_cycle == "yearly":
        return _add_period(start, years=1)
    else:
        raise ValueError(f"Unknown billing_cycle: {billing_cycle!r}")


def resolve_subscription_price(
    plan: SubscriptionPlan,
    org: Organization,
    db: Session,
    price_list_id_override: Optional[int] = None,
) -> Decimal:
    """
    Price resolution order:
    1. price_list_id_override (explicit caller-supplied list) if provided
    2. org.price_list_id (org's default list) if set
    3. item.unit_price (base price)
    """
    item = db.query(Item).filter(Item.id == plan.item_id).first()
    if item is None:
        raise ValueError(f"Item {plan.item_id} not found")

    effective_pl_id = price_list_id_override if price_list_id_override is not None else org.price_list_id
    if effective_pl_id:
        pli = db.query(PriceListItem).filter(
            PriceListItem.price_list_id == effective_pl_id,
            PriceListItem.item_id == plan.item_id,
        ).first()
        if pli:
            return Decimal(str(pli.unit_price))

    return Decimal(str(item.unit_price))


def create_subscription(
    db: Session,
    org_id: int,
    plan_id: int,
    start_date: date,
    price_list_id: Optional[int] = None,
) -> Subscription:
    """
    Create a new subscription for an org.
    - Fetches plan and org; raises ValueError if not found or inactive.
    - Computes period_end and next_billing_date.
    - If plan.trial_days > 0: status='trial', trial_end_date = start_date + trial_days.
    - Otherwise: status='active'.
    - Resolves unit_price via resolve_subscription_price (uses org price list or item base).
    - If price_list_id is explicitly provided, use it (overrides org's default).
    - Commits and returns the Subscription.
    """
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise ValueError(f"Subscription plan {plan_id} not found or inactive")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError(f"Organization {org_id} not found")

    unit_price = resolve_subscription_price(plan, org, db, price_list_id_override=price_list_id)

    # Compute dates
    period_end = compute_period_end(start_date, plan.billing_cycle)
    next_billing = compute_next_billing_date(period_end)

    # Trial logic
    if plan.trial_days > 0:
        status = "trial"
        trial_end = start_date + timedelta(days=plan.trial_days)
    else:
        status = "active"
        trial_end = None

    sub = Subscription(
        org_id=org_id,
        subscription_plan_id=plan_id,
        price_list_id=price_list_id,
        status=status,
        start_date=start_date,
        trial_end_date=trial_end,
        current_period_start=start_date,
        current_period_end=period_end,
        next_billing_date=next_billing,
        unit_price=unit_price,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def cancel_subscription(db: Session, subscription_id: int) -> Subscription:
    """
    Cancel a subscription:
    - Fetch subscription; raise ValueError if not found.
    - If status is already 'cancelled' or 'expired': raise ValueError.
    - Set status='cancelled', cancelled_at=datetime.utcnow().
    - Commit and return updated subscription.
    """
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found")
    if sub.status in ("cancelled", "expired"):
        raise ValueError(f"Subscription {subscription_id} is already {sub.status}")

    sub.status = "cancelled"
    sub.cancelled_at = datetime.utcnow()
    db.commit()
    db.refresh(sub)
    return sub
