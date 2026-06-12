from sqlalchemy import BigInteger, Column, String, Text, Integer, Date, DateTime, Enum, Boolean, DECIMAL, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    billing_cycle = Column(
        Enum("monthly", "quarterly", "yearly", name="sub_billing_cycle"),
        nullable=False,
        default="monthly",
        server_default="monthly",
    )
    tax_rate = Column(DECIMAL(5, 2), nullable=False, default="0.00", server_default="0.00")
    trial_days = Column(Integer, nullable=False, default=0, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    subscription_plan_id = Column(BigInteger, ForeignKey("subscription_plans.id"), nullable=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=True)
    status = Column(
        Enum("trial", "active", "past_due", "cancelled", "expired", name="subscription_status"),
        nullable=False,
        default="active",
        server_default="active",
    )
    billing_cycle = Column(
        Enum("monthly", "quarterly", "yearly"),
        nullable=False,
        default="monthly",
        server_default="monthly",
    )
    start_date = Column(Date, nullable=False)
    trial_end_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    current_period_start = Column(Date, nullable=False)
    current_period_end = Column(Date, nullable=False)
    next_billing_date = Column(Date, nullable=False)
    due_days = Column(Integer, nullable=False, default=15, server_default="15")
    tax_rate = Column(DECIMAL(5, 2), nullable=False, default="0.00", server_default="0.00")
    cancelled_at = Column(DateTime, nullable=True)
    unit_price = Column(DECIMAL(15, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
