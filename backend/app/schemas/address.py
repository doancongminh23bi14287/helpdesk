from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AddressCreate(BaseModel):
    label: str
    street: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: str = "Vietnam"
    postal_code: Optional[str] = None
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    is_default: Optional[bool] = None


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    label: str
    street: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    is_default: bool
    created_at: datetime
