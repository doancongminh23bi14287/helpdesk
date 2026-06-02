from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional
from datetime import date, datetime
from decimal import Decimal


class SubscriptionPlanCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    item_id: int
    billing_cycle: Literal["monthly", "quarterly", "yearly"] = "monthly"
    trial_days: int = 0
    is_active: bool = True


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    billing_cycle: Optional[Literal["monthly", "quarterly", "yearly"]] = None
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
    trial_days: int
    is_active: bool
    created_at: datetime


class SubscriptionCreate(BaseModel):
    org_id: int
    plan_id: int
    start_date: date
    price_list_id: Optional[int] = None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    org_id: int
    subscription_plan_id: int
    price_list_id: Optional[int] = None
    status: str
    start_date: date
    trial_end_date: Optional[date] = None
    current_period_start: date
    current_period_end: date
    next_billing_date: date
    cancelled_at: Optional[datetime] = None
    unit_price: Decimal
    created_at: datetime
    updated_at: datetime
    # enriched fields
    plan_name: Optional[str] = None
    org_name: Optional[str] = None
