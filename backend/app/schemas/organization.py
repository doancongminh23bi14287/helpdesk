# backend/app/schemas/organization.py
from typing import Optional
from datetime import datetime, date

from pydantic import BaseModel, ConfigDict


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
    contacts_count: int = 0
    addresses_count: int = 0


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    name: str
    type: str
    status: str
    domain: Optional[str] = None
    expiry_date: Optional[date] = None
    disk_usage: Optional[str] = None
    monthly_cost: Optional[float] = None
