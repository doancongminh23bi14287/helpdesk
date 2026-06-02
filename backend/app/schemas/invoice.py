from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


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
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # enriched
    org_name: Optional[str] = None
    subscription_plan_name: Optional[str] = None
    lines: List[InvoiceLineOut] = []
