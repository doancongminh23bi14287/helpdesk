from typing import Literal, Optional
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ItemCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    type: Literal["saas", "hosting", "domain", "support", "other"]
    unit_price: Decimal
    unit: str = "month"
    is_active: bool = True


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[Literal["saas", "hosting", "domain", "support", "other"]] = None
    unit_price: Optional[Decimal] = None
    unit: Optional[str] = None
    is_active: Optional[bool] = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: Optional[str] = None
    type: str
    unit_price: Decimal
    unit: str
    is_active: bool
    created_at: datetime
