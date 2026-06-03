# backend/app/schemas/user.py
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "customer"
    org_id: int
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    org_id: int
    phone: Optional[str] = None
    is_active: bool
    must_change_password: bool = False
    last_login_at: Optional[datetime] = None
    created_at: datetime
    linked_contact_id: Optional[int] = None
    linked_contact_name: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    new_password: str
