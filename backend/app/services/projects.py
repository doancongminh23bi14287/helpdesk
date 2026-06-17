from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectTask
from app.models.service import Service
from app.models.subscription import Subscription
from app.schemas.project import ProjectCreate, ProjectTaskCreate, ProjectTaskUpdate, ProjectUpdate


ALLOWED_TASK_TRANSITIONS = {
    "open": {"working", "review", "completed", "cancelled"},
    "working": {"review", "completed", "open", "cancelled"},
    "review": {"working", "approved", "completed", "cancelled"},
    "approved": {"completed", "working", "cancelled"},
    "completed": {"working"},
    "cancelled": set(),
}


def validate_project_links(db: Session, org_id: int, service_id: int | None, subscription_id: int | None) -> None:
    """Raise 422 if a linked service/subscription does not belong to the project org."""
    if service_id is not None:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service or service.org_id != org_id:
            raise HTTPException(status_code=422, detail="Service does not belong to the project organization")
    if subscription_id is not None:
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription or subscription.org_id != org_id:
            raise HTTPException(status_code=422, detail="Subscription does not belong to the project organization")


def calculate_project_progress(db: Session, project_id: int) -> float:
    """Return percent of non-cancelled tasks completed (0.0 when no active tasks)."""
    tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
    active = [t for t in tasks if t.status != "cancelled"]
    if not active:
        return 0.0
    completed = sum(1 for t in active if t.status == "completed")
    return round(completed / len(active) * 100, 2)


def recompute_project_progress(db: Session, project_id: int) -> Project:
    """Refresh progress_percent and derive project status from its active tasks."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
    active = [t for t in tasks if t.status != "cancelled"]
    project.progress_percent = calculate_project_progress(db, project_id)

    if project.status != "cancelled":
        if active and all(t.status == "completed" for t in active):
            project.status = "completed"
        elif any(t.status in {"working", "review"} for t in active):
            project.status = "working"
        elif project.status == "completed" and active:
            project.status = "open"

    db.flush()
    return project


def create_project(db: Session, payload: ProjectCreate, created_by: int) -> Project:
    """Create a project after validating its service/subscription links."""
    validate_project_links(db, payload.org_id, payload.service_id, payload.subscription_id)
    project = Project(
        org_id=payload.org_id,
        service_id=payload.service_id,
        subscription_id=payload.subscription_id,
        name=payload.name.strip(),
        description=payload.description,
        project_type=payload.project_type,
        status=payload.status,
        visibility=payload.visibility,
        start_date=payload.start_date,
        due_date=payload.due_date,
        project_manager_id=payload.project_manager_id,
        created_by=created_by,
    )
    db.add(project)
    db.flush()
    return project


def update_project(db: Session, project: Project, payload: ProjectUpdate) -> Project:
    """Apply a partial update to a project, re-validating links."""
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    validate_project_links(
        db,
        project.org_id,
        data.get("service_id", project.service_id),
        data.get("subscription_id", project.subscription_id),
    )
    for field, value in data.items():
        setattr(project, field, value)
    db.flush()
    return project


def cancel_project(db: Session, project: Project) -> Project:
    """Mark a project as cancelled."""
    project.status = "cancelled"
    db.flush()
    return project


def create_project_task(db: Session, project: Project, payload: ProjectTaskCreate, created_by: int) -> ProjectTask:
    """Create a task under a project and recompute project progress."""
    task = ProjectTask(
        project_id=project.id,
        title=payload.title.strip(),
        description=payload.description,
        task_type=payload.task_type,
        assignee_id=payload.assignee_id,
        status=payload.status,
        priority=payload.priority,
        is_client_visible=payload.is_client_visible,
        internal_note=payload.internal_note,
        start_date=payload.start_date,
        due_date=payload.due_date,
        created_by=created_by,
    )
    if task.status == "completed":
        task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(task)
    db.flush()
    recompute_project_progress(db, project.id)
    return task


def _validate_task_transition(current_status: str, next_status: str) -> None:
    if current_status == next_status:
        return
    if next_status not in ALLOWED_TASK_TRANSITIONS.get(current_status, set()):
        raise HTTPException(status_code=422, detail=f"Invalid task status transition: {current_status} -> {next_status}")


def update_project_task(db: Session, task: ProjectTask, payload: ProjectTaskUpdate) -> ProjectTask:
    """Apply a partial update to a task, validating any status transition."""
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        _validate_task_transition(task.status, data["status"])
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()
    for field, value in data.items():
        setattr(task, field, value)
    if "status" in data:
        task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None) if task.status == "completed" else None
    db.flush()
    recompute_project_progress(db, task.project_id)
    return task


def update_project_task_status(db: Session, task: ProjectTask, status: str) -> ProjectTask:
    """Transition a task to a new status (validated) and recompute progress."""
    _validate_task_transition(task.status, status)
    task.status = status
    task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None) if status == "completed" else None
    db.flush()
    recompute_project_progress(db, task.project_id)
    return task


def cancel_project_task(db: Session, task: ProjectTask) -> ProjectTask:
    """Cancel a task and recompute project progress without it."""
    task.status = "cancelled"
    task.completed_at = None
    db.flush()
    recompute_project_progress(db, task.project_id)
    return task
