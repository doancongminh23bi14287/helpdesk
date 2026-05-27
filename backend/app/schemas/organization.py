# backend/app/schemas/organization.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date


class OrganizationCreate(BaseModel):
    name: str
    code: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    name: str
    type: str
    status: str
    domain: Optional[str] = None
    expiry_date: Optional[date] = None
