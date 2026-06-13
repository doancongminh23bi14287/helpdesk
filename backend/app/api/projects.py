from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.scoping import (
    assert_org_access,
    assert_project_access,
    assert_project_task_access,
    get_accessible_org_ids,
    scope_project_tasks,
    scope_projects,
)
from app.database import get_db
from app.models.organization import Organization
from app.models.project import Project, ProjectDocument, ProjectTask
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectTaskCreate,
    ProjectTaskStatusUpdate,
    ProjectTaskUpdate,
    ProjectUpdate,
)
from app.services.file_storage import get_attachment_path, save_attachment
from app.services.projects import (
    cancel_project,
    cancel_project_task,
    create_project,
    create_project_task,
    update_project,
    update_project_task,
    update_project_task_status,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])
task_router = APIRouter(prefix="/api/project-tasks", tags=["project-tasks"])


def _require_internal(user: User) -> None:
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Customers cannot manage projects")


def _can_manage_project(project: Project, user: User, db: Session) -> bool:
    if user.role == "admin":
        return True
    if user.role != "staff":
        return False
    org_ids = get_accessible_org_ids(user, db) or []
    return project.org_id in org_ids


def _project_dict(project: Project, db: Session, user: User, detail: bool = False) -> dict:
    org = db.query(Organization).filter(Organization.id == project.org_id).first()
    manager = db.query(User).filter(User.id == project.project_manager_id).first() if project.project_manager_id else None
    base = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "project_type": project.project_type,
        "status": project.status,
        "visibility": project.visibility,
        "start_date": project.start_date,
        "due_date": project.due_date,
        "progress_percent": float(project.progress_percent or 0),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    if user.role == "customer":
        return base
    base.update({
        "org_id": project.org_id,
        "org_name": org.name if org else None,
        "service_id": project.service_id,
        "subscription_id": project.subscription_id,
        "created_by": project.created_by,
        "project_manager_id": project.project_manager_id,
        "project_manager_name": manager.full_name if manager else None,
    })
    return base


def _task_dict(task: ProjectTask, db: Session, user: User) -> dict:
    base = {
        "id": task.id,
        "project_id": task.project_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "is_client_visible": task.is_client_visible,
        "start_date": task.start_date,
        "due_date": task.due_date,
        "completed_at": task.completed_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
    if user.role == "customer":
        base.pop("is_client_visible", None)
        return base
    assignee = db.query(User).filter(User.id == task.assignee_id).first() if task.assignee_id else None
    base.update({
        "assignee_id": task.assignee_id,
        "assignee_name": assignee.full_name if assignee else None,
        "assignee_email": assignee.email if assignee else None,
        "internal_note": task.internal_note,
        "created_by": task.created_by,
    })
    return base


def _document_dict(document: ProjectDocument, db: Session, user: User) -> dict:
    base = {
        "id": document.id,
        "project_id": document.project_id,
        "file_name": document.file_name,
        "file_size": document.file_size,
        "mime_type": document.mime_type,
        "detected_mime": document.detected_mime,
        "sha256": document.sha256,
        "is_client_visible": document.is_client_visible,
        "created_at": document.created_at,
    }
    if user.role != "customer":
        uploader = db.query(User).filter(User.id == document.uploaded_by).first()
        base.update({
            "uploaded_by": document.uploaded_by,
            "uploader_name": uploader.full_name if uploader else None,
            "uploader_email": uploader.email if uploader else None,
        })
    return base


@router.get("")
def list_projects(
    status: Optional[str] = None,
    project_type: Optional[str] = None,
    org_id: Optional[int] = None,
    service_id: Optional[int] = None,
    subscription_id: Optional[int] = None,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = scope_projects(db.query(Project), user, db, include_internal=user.role in {"admin", "staff"})
    if status:
        query = query.filter(Project.status == status)
    if project_type:
        query = query.filter(Project.project_type == project_type)
    if org_id:
        query = query.filter(Project.org_id == org_id)
    if service_id:
        query = query.filter(Project.service_id == service_id)
    if subscription_id:
        query = query.filter(Project.subscription_id == subscription_id)
    if q:
        term = f"%{q}%"
        query = query.filter(or_(Project.name.ilike(term), Project.description.ilike(term)))

    query = query.order_by(Project.updated_at.desc(), Project.id.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [_project_dict(project, db, user) for project in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total else 1,
    }


@router.post("", status_code=201)
def create_project_endpoint(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    assert_org_access(payload.org_id, user, db)
    project = create_project(db, payload, created_by=user.id)
    db.commit()
    db.refresh(project)
    return _project_dict(project, db, user, detail=True)


@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = assert_project_access(project_id, user, db)
    return _project_dict(project, db, user, detail=True)


@router.patch("/{project_id}")
def update_project_endpoint(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    project = assert_project_access(project_id, user, db)
    if not _can_manage_project(project, user, db):
        raise HTTPException(status_code=404, detail="Project not found")
    project = update_project(db, project, payload)
    db.commit()
    db.refresh(project)
    return _project_dict(project, db, user, detail=True)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can cancel projects")
    project = assert_project_access(project_id, user, db)
    project = cancel_project(db, project)
    db.commit()
    db.refresh(project)
    return _project_dict(project, db, user, detail=True)


@router.get("/{project_id}/tasks")
def list_project_tasks(
    project_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = assert_project_access(project_id, user, db)
    query = scope_project_tasks(
        db.query(ProjectTask).filter(ProjectTask.project_id == project.id),
        user,
        db,
        include_internal=user.role in {"admin", "staff"},
    )
    if status:
        query = query.filter(ProjectTask.status == status)
    tasks = query.order_by(ProjectTask.due_date.asc(), ProjectTask.id.asc()).all()
    return [_task_dict(task, db, user) for task in tasks]


@router.get("/{project_id}/tickets")
def list_project_tickets(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all non-deleted tickets linked to this project."""
    project = assert_project_access(project_id, user, db)
    from app.models.ticket import Ticket
    query = db.query(Ticket).filter(
        Ticket.project_id == project.id,
        Ticket.is_deleted == False,  # noqa: E712
    )
    if user.role == "customer":
        query = query.filter(Ticket.org_id == user.org_id)
    tickets = query.order_by(Ticket.created_at.desc()).limit(50).all()
    from app.api.tickets import _enrich_tickets
    _enrich_tickets(tickets, db)
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at,
        }
        for t in tickets
    ]


@router.post("/{project_id}/tasks", status_code=201)
def create_project_task_endpoint(
    project_id: int,
    payload: ProjectTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    project = assert_project_access(project_id, user, db)
    if not _can_manage_project(project, user, db):
        raise HTTPException(status_code=404, detail="Project not found")
    task = create_project_task(db, project, payload, created_by=user.id)
    db.commit()
    db.refresh(task)
    return _task_dict(task, db, user)


@router.get("/{project_id}/documents")
def list_project_documents(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = assert_project_access(project_id, user, db)
    query = db.query(ProjectDocument).filter(ProjectDocument.project_id == project.id)
    if user.role == "customer":
        query = query.filter(ProjectDocument.is_client_visible.is_(True))
    rows = query.order_by(ProjectDocument.created_at.desc(), ProjectDocument.id.desc()).all()
    return [_document_dict(row, db, user) for row in rows]


@router.post("/{project_id}/documents", status_code=201)
async def upload_project_document(
    project_id: int,
    file: UploadFile = File(...),
    is_client_visible: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    project = assert_project_access(project_id, user, db)
    if not _can_manage_project(project, user, db):
        raise HTTPException(status_code=404, detail="Project not found")

    data = await file.read()
    stored = save_attachment(
        data,
        org_id=project.org_id,
        original_filename=file.filename or "document",
        mime_type=file.content_type or "application/octet-stream",
    )
    document = ProjectDocument(
        project_id=project.id,
        file_name=file.filename or "document",
        file_path=stored["stored_path"],
        file_size=stored["file_size"],
        mime_type=file.content_type or "application/octet-stream",
        detected_mime=stored["detected_mime"],
        sha256=stored["sha256"],
        is_client_visible=is_client_visible,
        uploaded_by=user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _document_dict(document, db, user)


@router.get("/{project_id}/documents/{document_id}/download")
def download_project_document(
    project_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = assert_project_access(project_id, user, db)
    document = db.query(ProjectDocument).filter(
        ProjectDocument.id == document_id,
        ProjectDocument.project_id == project.id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Project document not found")
    if user.role == "customer" and not document.is_client_visible:
        raise HTTPException(status_code=404, detail="Project document not found")

    abs_path = get_attachment_path(document.file_path)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(abs_path),
        filename=document.file_name,
        media_type=document.mime_type,
        content_disposition_type="attachment",
    )


@task_router.get("/{task_id}")
def get_project_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = assert_project_task_access(task_id, user, db)
    return _task_dict(task, db, user)


@task_router.patch("/{task_id}")
def update_project_task_endpoint(
    task_id: int,
    payload: ProjectTaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    task = assert_project_task_access(task_id, user, db)
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project or not _can_manage_project(project, user, db):
        raise HTTPException(status_code=404, detail="Project task not found")
    task = update_project_task(db, task, payload)
    db.commit()
    db.refresh(task)
    return _task_dict(task, db, user)


@task_router.patch("/{task_id}/status")
def update_project_task_status_endpoint(
    task_id: int,
    payload: ProjectTaskStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Project task not found")
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project task not found")
    if user.role != "admin":
        org_ids = get_accessible_org_ids(user, db) or []
        if project.org_id not in org_ids and task.assignee_id != user.id:
            raise HTTPException(status_code=404, detail="Project task not found")
    task = update_project_task_status(db, task, payload.status)
    db.commit()
    db.refresh(task)
    return _task_dict(task, db, user)


@task_router.delete("/{task_id}")
def delete_project_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can cancel project tasks")
    task = assert_project_task_access(task_id, user, db)
    task = cancel_project_task(db, task)
    db.commit()
    db.refresh(task)
    return _task_dict(task, db, user)
