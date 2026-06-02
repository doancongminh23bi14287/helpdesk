from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional
from datetime import datetime


class ContactCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Literal["primary", "billing", "technical", "other"] = "primary"
    is_active: bool = True


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[Literal["primary", "billing", "technical", "other"]] = None
    is_active: Optional[bool] = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
