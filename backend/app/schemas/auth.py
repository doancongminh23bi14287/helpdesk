# backend/app/schemas/auth.py
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    org_id: int
    must_change_password: bool = False
    phone: Optional[str] = None
    org_name: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_color: Optional[str] = None


class UpdateMeRequest(BaseModel):
    """Fields a user may update on their own profile.

    Email, role, org_id, is_active, password_hash, must_change_password are
    intentionally absent — privilege escalation guard.
    """
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_color: Optional[str] = None


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class LoginHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    email: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    created_at: datetime
