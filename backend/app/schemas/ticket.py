# backend/app/schemas/ticket.py
from typing import Literal, Optional, List
from datetime import datetime, date

from pydantic import BaseModel, ConfigDict, field_validator


# Allowed values mirror the MariaDB enum on `tickets.ticket_type`.
# Update 3 nơi in lockstep: model (models/ticket.py), schema (here), frontend (NewTicketPage.jsx).
# Adding a value here without a migration will still 500.
TicketTypeLiteral = Literal[
    "Question",
    "Bug",
    "Incident",
    "Task Request",
    "Change Request",
    "Feature Request",
    "Content Request",
    "SEO Request",
    "Approval Required",
    "Complaint",
    "Renewal",
    "Other",
]

AssignmentModeLiteral = Literal["none", "auto", "manual"]


class TicketAssigneeOut(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool


class TicketCreate(BaseModel):
    org_id: int
    service_id: Optional[int] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    requested_item_id: Optional[int] = None
    subject: str
    description: Optional[str] = None
    priority: str = "Medium"
    ticket_type: TicketTypeLiteral = "Question"
    # Legacy single-assignee (deprecated but still accepted — treated as assignee_ids=[assignee_id])
    assignee_id: Optional[int] = None
    # Multi-assignee
    assignee_ids: Optional[List[int]] = None
    assignment_mode: Optional[AssignmentModeLiteral] = None

    @field_validator("ticket_type", mode="before")
    @classmethod
    def default_ticket_type(cls, v):
        if v is None:
            return "Question"
        if isinstance(v, str) and not v.strip():
            return "Question"
        return v


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = None
    priority: Optional[str] = None
    task_id: Optional[int] = None
    # Legacy single-assignee (deprecated but still accepted)
    assignee_id: Optional[int] = None
    # Multi-assignee
    assignee_ids: Optional[List[int]] = None
    assignment_mode: Optional[AssignmentModeLiteral] = None


class TicketActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    actor_id: Optional[int] = None
    action: str
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime


class TicketReplyCreate(BaseModel):
    content: str
    is_internal: bool = False


class TicketReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author_id: Optional[int] = None
    author_email: Optional[str] = None
    author_name: Optional[str] = None
    content: str
    is_internal: bool
    source: str
    created_at: datetime


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    org_name: Optional[str] = None
    org_code: Optional[str] = None
    service_id: Optional[int] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    service_name: Optional[str] = None
    service_type: Optional[str] = None
    service_status: Optional[str] = None
    subject: str
    description: Optional[str] = None
    status: str
    priority: str
    ticket_type: str
    source: str
    raised_by: Optional[int] = None
    raised_by_email: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    assignee_email: Optional[str] = None
    assignment_mode: Optional[str] = None
    assignees: List[TicketAssigneeOut] = []
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class TicketAssignPayload(BaseModel):
    assignee_id: int


class TicketDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    org_name: Optional[str] = None
    org_code: Optional[str] = None
    service_id: Optional[int] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    service_name: Optional[str] = None
    service_type: Optional[str] = None
    service_status: Optional[str] = None
    service_expiry_date: Optional[date] = None
    service_monthly_cost: Optional[float] = None
    service_disk_usage: Optional[str] = None
    subject: str
    description: Optional[str] = None
    status: str
    priority: str
    ticket_type: str
    source: str
    raised_by: Optional[int] = None
    raised_by_email: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    assignee_email: Optional[str] = None
    assignment_mode: Optional[str] = None
    assignees: List[TicketAssigneeOut] = []
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    replies: List[TicketReplyOut] = []
    activities: List[TicketActivityOut] = []


class LinkProjectPayload(BaseModel):
    project_id: int


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: Optional[int] = None
    reply_id: Optional[int] = None
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    detected_mime: Optional[str] = None
    sha256: Optional[str] = None
    uploaded_by: int
    created_at: datetime
