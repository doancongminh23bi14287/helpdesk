from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

PROJECT_TYPES = {"seo", "website", "hosting", "maintenance", "other"}
PROJECT_STATUSES = {"open", "working", "on_hold", "completed", "cancelled"}
PROJECT_VISIBILITIES = {"internal", "customer_visible"}
TASK_TYPES = {
    "keyword_research",
    "technical_audit",
    "on_page",
    "content",
    "backlink",
    "report",
    "design",
    "development",
    "deployment",
    "support",
    "other",
}
TASK_STATUSES = {"open", "working", "review", "completed", "cancelled"}
TASK_PRIORITIES = {"low", "medium", "high", "urgent"}


def _non_empty(value: Optional[str], field: str) -> Optional[str]:
    if value is not None and not value.strip():
        raise ValueError(f"{field} cannot be empty")
    return value


def _allowed(value: Optional[str], allowed: set[str], field: str) -> Optional[str]:
    if value is not None and value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return value


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: int
    service_id: Optional[int] = None
    subscription_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    project_type: str = "seo"
    status: str = "open"
    visibility: str = "customer_visible"
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    project_manager_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _non_empty(value, "name")

    @field_validator("project_type")
    @classmethod
    def validate_project_type(cls, value: str) -> str:
        return _allowed(value, PROJECT_TYPES, "project_type")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _allowed(value, PROJECT_STATUSES, "status")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        return _allowed(value, PROJECT_VISIBILITIES, "visibility")


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: Optional[int] = None
    subscription_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    visibility: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    project_manager_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        return _non_empty(value, "name")

    @field_validator("project_type")
    @classmethod
    def validate_project_type(cls, value: Optional[str]) -> Optional[str]:
        return _allowed(value, PROJECT_TYPES, "project_type")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        return _allowed(value, PROJECT_STATUSES, "status")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: Optional[str]) -> Optional[str]:
        return _allowed(value, PROJECT_VISIBILITIES, "visibility")


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    service_id: Optional[int] = None
    subscription_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    project_type: str
    status: str
    visibility: str
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    progress_percent: float
    created_by: int
    project_manager_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ProjectListItem(ProjectRead):
    org_name: Optional[str] = None
    project_manager_name: Optional[str] = None


class ProjectTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: Optional[str] = None
    task_type: str = "other"
    assignee_id: Optional[int] = None
    status: str = "open"
    priority: str = "medium"
    is_client_visible: bool = False
    internal_note: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _non_empty(value, "title")

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        return _allowed(value, TASK_TYPES, "task_type")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _allowed(value, TASK_STATUSES, "status")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        return _allowed(value, TASK_PRIORITIES, "priority")


class ProjectTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    assignee_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    is_client_visible: Optional[bool] = None
    internal_note: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        return _non_empty(value, "title")

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: Optional[str]) -> Optional[str]:
        return _allowed(value, TASK_TYPES, "task_type")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        return _allowed(value, TASK_STATUSES, "status")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: Optional[str]) -> Optional[str]:
        return _allowed(value, TASK_PRIORITIES, "priority")


class ProjectTaskStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _allowed(value, TASK_STATUSES, "status")


class ProjectTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: Optional[str] = None
    task_type: str
    assignee_id: Optional[int] = None
    status: str
    priority: str
    is_client_visible: bool
    internal_note: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ProjectTaskListItem(ProjectTaskRead):
    assignee_name: Optional[str] = None
    assignee_email: Optional[str] = None


class ProjectDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    file_name: str
    file_size: int
    mime_type: str
    detected_mime: Optional[str] = None
    sha256: Optional[str] = None
    is_client_visible: bool
    uploaded_by: int
    uploader_name: Optional[str] = None
    uploader_email: Optional[str] = None
    created_at: datetime
