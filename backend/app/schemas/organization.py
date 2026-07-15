# backend/app/schemas/organization.py
from typing import Optional, Literal
from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
    subscription_id: Optional[int] = None
    is_archived: bool = False
    archived_at: Optional[datetime] = None
    archived_by_id: Optional[int] = None
    can_hard_delete: bool = False
    dependency_reason: Optional[str] = None
    dependency_details: list[str] = Field(default_factory=list)


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[Literal["saas", "hosting", "domain", "support", "other"]] = None
    domain: Optional[str] = None
    expiry_date: Optional[date] = None
    disk_usage: Optional[str] = None
    monthly_cost: Optional[Decimal] = None
    billing_cycle: Optional[Literal["monthly", "quarterly", "yearly"]] = None
