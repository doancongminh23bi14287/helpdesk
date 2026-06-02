from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional, List
from datetime import datetime
from decimal import Decimal


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


class PriceListCreate(BaseModel):
    name: str
    currency: str = "VND"
    is_active: bool = True


class PriceListItemCreate(BaseModel):
    item_id: int
    unit_price: Decimal


class PriceListItemUpdate(BaseModel):
    unit_price: Decimal


class PriceListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price_list_id: int
    item_id: int
    unit_price: Decimal
    item: Optional[ItemOut] = None


class PriceListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: str
    is_active: bool
    created_at: datetime


class PriceListWithItems(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: str
    is_active: bool
    created_at: datetime
    items: List[PriceListItemOut] = []
