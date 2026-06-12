import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.item import Item
from app.models.organization import Organization

logger = logging.getLogger(__name__)


def compute_next_billing_date(current_period_end: date) -> date:
    """Return the day after the current period ends."""
    return current_period_end + timedelta(days=1)


def _add_period(start: date, months: int = 0, years: int = 0) -> date:
    return start + relativedelta(months=months, years=years)


def compute_period_end(start: date, billing_cycle: str) -> date:
    """Return the period end for a billing cycle (monthly/quarterly/yearly)."""
    if billing_cycle == "monthly":
        return _add_period(start, months=1)
    elif billing_cycle == "quarterly":
        return _add_period(start, months=3)
    elif billing_cycle == "yearly":
        return _add_period(start, years=1)
    else:
        raise ValueError(f"Unknown billing_cycle: {billing_cycle!r}")


def create_subscription(
    db: Session,
    org_id: int,
    plan_id: int,
    start_date: date,
    billing_cycle: Optional[str] = None,
    due_days: int = 15,
    tax_rate: Decimal = Decimal("0.00"),
    end_date: Optional[date] = None,
) -> Subscription:
    """
    plan_id is an item_id. unit_price = item.unit_price adjusted per cycle:
    quarterly ×3×0.95, yearly ×12×0.8. Prepaid: next_billing_date = start_date.
    """
    item = db.query(Item).filter(Item.id == plan_id, Item.is_active.is_(True)).first()
    if not item:
        raise ValueError(f"Item {plan_id} not found or inactive")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError(f"Organization {org_id} not found")

    effective_cycle = billing_cycle or "monthly"
    monthly_price = Decimal(str(item.unit_price))

    if effective_cycle == "quarterly":
        unit_price = round(monthly_price * 3 * Decimal("0.95"), 2)
    elif effective_cycle == "yearly":
        unit_price = round(monthly_price * 12 * Decimal("0.8"), 2)
    else:
        unit_price = monthly_price

    period_end = compute_period_end(start_date, effective_cycle)

    sub = Subscription(
        org_id=org_id,
        subscription_plan_id=None,
        item_id=item.id,
        status="active",
        billing_cycle=effective_cycle,
        start_date=start_date,
        trial_end_date=None,
        end_date=end_date,
        current_period_start=start_date,
        current_period_end=period_end,
        next_billing_date=period_end,
        due_days=due_days,
        tax_rate=tax_rate,
        unit_price=unit_price,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    try:
        from app.services.invoice_service import create_invoice_from_subscription
        create_invoice_from_subscription(sub.id, db)
    except Exception as e:
        logger.warning(
            "First invoice creation failed for subscription %s: %s. "
            "Invoice can be generated manually.",
            sub.id, e,
        )

    return sub


def cancel_subscription(db: Session, subscription_id: int) -> Subscription:
    """Cancel an active subscription; raises ValueError if missing or already ended."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found")
    if sub.status in ("cancelled", "expired"):
        raise ValueError(f"Subscription {subscription_id} is already {sub.status}")

    sub.status = "cancelled"
    sub.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(sub)
    return sub
