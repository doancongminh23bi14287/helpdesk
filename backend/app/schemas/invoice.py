from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

VALID_PAYMENT_METHODS = {"bank_transfer", "cash", "vnpay", "manual", "other"}


class InvoiceLineIn(BaseModel):
    item_id: Optional[int] = None
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal


class InvoiceCreate(BaseModel):
    org_id: int
    notes: Optional[str] = None
    lines: List[InvoiceLineIn]


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_id: int
    item_id: Optional[int] = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_number: str
    org_id: int
    subscription_id: Optional[int] = None
    status: str
    issue_date: date
    due_date: date
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    notes: Optional[str] = None
    cancel_reason: Optional[str] = None
    paid_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # enriched
    org_name: Optional[str] = None
    subscription_plan_name: Optional[str] = None
    lines: List[InvoiceLineOut] = []


class InvoiceUpdate(BaseModel):
    notes: Optional[str] = None
    due_date: Optional[date] = None
    issue_date: Optional[date] = None


class CancelPayload(BaseModel):
    cancel_reason: str


class PaymentCreate(BaseModel):
    amount: Decimal
    method: str
    reference: Optional[str] = None
    note: Optional[str] = None
    paid_at: Optional[datetime] = None

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        if v not in VALID_PAYMENT_METHODS:
            raise ValueError(
                f"method must be one of: {', '.join(sorted(VALID_PAYMENT_METHODS))}"
            )
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_id: int
    amount: Decimal
    method: str
    reference: Optional[str] = None
    paid_by: Optional[int] = None
    note: Optional[str] = None
    paid_at: datetime
    created_at: datetime
