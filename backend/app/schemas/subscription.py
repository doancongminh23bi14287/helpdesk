from typing import Literal, Optional
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SubscriptionPlanCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    item_id: int
    billing_cycle: Literal["monthly", "quarterly", "yearly"] = "monthly"
    tax_rate: Decimal = Decimal("0.00")
    trial_days: int = 0
    is_active: bool = True


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    billing_cycle: Optional[Literal["monthly", "quarterly", "yearly"]] = None
    tax_rate: Optional[Decimal] = None
    trial_days: Optional[int] = None
    is_active: Optional[bool] = None


class SubscriptionPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: Optional[str] = None
    item_id: int
    billing_cycle: str
    tax_rate: Decimal
    trial_days: int
    is_active: bool
    created_at: datetime
    unit_price: Optional[Decimal] = None


class SubscriptionCreate(BaseModel):
    org_id: int
    plan_id: int
    start_date: date
    billing_cycle: Optional[Literal["monthly", "quarterly", "yearly"]] = None
    due_days: int = 15
    tax_rate: Decimal = Decimal("0.00")
    end_date: Optional[date] = None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    org_id: int
    subscription_plan_id: Optional[int] = None
    item_id: Optional[int] = None
    status: str
    billing_cycle: str
    start_date: date
    trial_end_date: Optional[date] = None
    end_date: Optional[date] = None
    current_period_start: date
    current_period_end: date
    next_billing_date: date
    due_days: int
    tax_rate: Decimal
    cancelled_at: Optional[datetime] = None
    unit_price: Decimal
    created_at: datetime
    updated_at: datetime
    # enriched fields
    plan_name: Optional[str] = None
    org_name: Optional[str] = None
