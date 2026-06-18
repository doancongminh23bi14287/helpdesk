from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.scoping import (
    assert_org_access,
    assert_project_access,
    assert_project_task_access,
    get_accessible_org_ids,
    scope_project_tasks,
    scope_projects,
    scope_tickets,
)
from app.database import get_db
from app.models.organization import Organization
from app.models.project import Project, ProjectDocument, ProjectMember, ProjectTask, TaskComment, TaskActivity, TaskAssignee, TaskApproval
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectDiscussionCreate,
    ProjectMemberCreate,
    ProjectTaskCreate,
    ProjectTaskCreateV2,
    ProjectTaskStatusUpdate,
    ProjectTaskUpdate,
    ProjectUpdate,
    TaskApprovalCreate,
    TaskApprovalOut,
    TaskCommentCreate,
    TaskCommentOut,
    TaskActivityOut,
    TaskAssigneeOut,
    ProjectTaskDetailOut,
)
from app.services.assignment import set_task_assignees, load_assignees_for_tasks
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


def _task_dict(task: ProjectTask, db: Session, user: User, assignees: list | None = None) -> dict:
    if assignees is None:
        assignees = load_assignees_for_tasks(db, [task.id]).get(task.id, [])
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
        "assignees": assignees,
        "comments_count": db.query(TaskComment).filter(TaskComment.task_id == task.id).count(),
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


def _task_detail_dict(task: ProjectTask, db: Session, user: User) -> dict:
    """Full task dict with comments and activities."""
    assignees = load_assignees_for_tasks(db, [task.id]).get(task.id, [])

    comment_query = db.query(TaskComment).filter(TaskComment.task_id == task.id)
    if user.role == "customer":
        comment_query = comment_query.filter(TaskComment.is_internal == False)  # noqa: E712
    comments_raw = comment_query.order_by(TaskComment.created_at.asc()).all()

    author_ids = {c.author_id for c in comments_raw if c.author_id}
    authors = {u.id: u for u in db.query(User).filter(User.id.in_(author_ids)).all()} if author_ids else {}
    comments = [
        {
            "id": c.id,
            "task_id": c.task_id,
            "author_id": c.author_id,
            "author_name": authors[c.author_id].full_name if c.author_id and c.author_id in authors else None,
            "content": c.content,
            "is_internal": c.is_internal,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in comments_raw
    ]

    activities_raw = (
        db.query(TaskActivity).filter(TaskActivity.task_id == task.id)
        .order_by(TaskActivity.created_at.asc()).all()
    )
    actor_ids = {a.actor_id for a in activities_raw if a.actor_id}
    actors = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}
    activities = [
        {
            "id": a.id,
            "task_id": a.task_id,
            "actor_id": a.actor_id,
            "actor_name": actors[a.actor_id].full_name if a.actor_id and a.actor_id in actors else None,
            "action": a.action,
            "from_value": a.from_value,
            "to_value": a.to_value,
            "detail": a.detail,
            "created_at": a.created_at,
        }
        for a in activities_raw
    ]

    base = _task_dict(task, db, user, assignees=assignees)
    base["comments"] = comments
    base["activities"] = activities
    return base


def _document_dict(document: ProjectDocument, db: Session, user: User) -> dict:
    from app.models.attachment import TicketAttachment
    ticket_id = None
    if document.ticket_attachment_id:
        att = db.query(TicketAttachment).filter(TicketAttachment.id == document.ticket_attachment_id).first()
        if att:
            ticket_id = att.ticket_id
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
        "source": document.source if document.source else "upload",
        "ticket_attachment_id": document.ticket_attachment_id,
        "ticket_id": ticket_id,
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
    query = scope_tickets(query, user, db)
    tickets = query.order_by(Ticket.created_at.desc()).limit(50).all()
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
    payload: ProjectTaskCreateV2,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    project = assert_project_access(project_id, user, db)
    if not _can_manage_project(project, user, db):
        raise HTTPException(status_code=404, detail="Project not found")
    task = create_project_task(db, project, payload, created_by=user.id)
    db.flush()

    # Multi-assignee support
    eff_ids: list[int] = []
    if payload.assignee_ids:
        eff_ids = list(payload.assignee_ids)
    elif payload.assignee_id is not None:
        eff_ids = [payload.assignee_id]
    if eff_ids:
        set_task_assignees(db, task, eff_ids, assigned_by=user.id)

    db.add(TaskActivity(
        task_id=task.id,
        actor_id=user.id,
        action="created",
        detail=f"Task created by {user.full_name or user.email}",
    ))
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
@limiter.limit("20/minute")
async def upload_project_document(
    request: Request,
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


def _assert_customer_project_member(project: Project, user: User, db: Session) -> None:
    """Raise 404 if a customer user is not an explicit ProjectMember.

    Non-customer callers pass through immediately — org-level access has already
    been verified by assert_project_task_access / scope_project_tasks at that point.
    """
    if user.role != "customer":
        return
    is_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user.id,
    ).first()
    if not is_member:
        raise HTTPException(status_code=404, detail="Task not found")


def _member_dict(member: ProjectMember, db: Session) -> dict:
    user = db.query(User).filter(User.id == member.user_id).first()
    return {
        "id": member.id,
        "project_id": member.project_id,
        "user_id": member.user_id,
        "user_full_name": user.full_name if user else None,
        "user_email": user.email if user else None,
        "role": member.role,
        "added_by": member.added_by,
        "created_at": member.created_at,
    }


@router.get("/{project_id}/members")
def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = assert_project_access(project_id, user, db)
    _assert_customer_project_member(project, user, db)
    members = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id)
        .order_by(ProjectMember.created_at.asc())
        .all()
    )
    user_ids = [m.user_id for m in members]
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
    return [
        {
            "id": m.id,
            "project_id": m.project_id,
            "user_id": m.user_id,
            "user_full_name": users.get(m.user_id, None) and users[m.user_id].full_name,
            "user_email": users.get(m.user_id, None) and users[m.user_id].email,
            "role": m.role,
            "added_by": m.added_by,
            "created_at": m.created_at,
        }
        for m in members
    ]


@router.post("/{project_id}/members", status_code=201)
def add_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    project = assert_project_access(project_id, user, db)
    if not _can_manage_project(project, user, db):
        raise HTTPException(status_code=403, detail="Cannot manage this project")

    target = db.query(User).filter(User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate: target must be in same org as project, OR be a staff/admin
    if target.role == "customer" and target.org_id != project.org_id:
        raise HTTPException(
            status_code=422,
            detail="Customer user must belong to the project's organization",
        )

    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == payload.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this project")

    member = ProjectMember(
        project_id=project.id,
        user_id=payload.user_id,
        role=payload.role,
        added_by=user.id,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_dict(member, db)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_project_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_internal(user)
    project = assert_project_access(project_id, user, db)
    if not _can_manage_project(project, user, db):
        raise HTTPException(status_code=403, detail="Cannot manage this project")

    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(member)
    db.commit()


@task_router.get("/{task_id}")
def get_project_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = assert_project_task_access(task_id, user, db)
    project = db.query(Project).filter(Project.id == task.project_id).first()
    _assert_customer_project_member(project, user, db)
    return _task_detail_dict(task, db, user)


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

    old_status = task.status
    task = update_project_task(db, task, payload)

    if task.status != old_status:
        db.add(TaskActivity(
            task_id=task.id,
            actor_id=user.id,
            action="status_change",
            from_value=old_status,
            to_value=task.status,
        ))

    # Multi-assignee update
    changes = payload.model_dump(exclude_unset=True)
    if "assignee_ids" in changes and changes["assignee_ids"] is not None:
        set_task_assignees(db, task, list(changes["assignee_ids"]), assigned_by=user.id)
    elif "assignee_id" in changes and changes["assignee_id"] is not None:
        set_task_assignees(db, task, [changes["assignee_id"]], assigned_by=user.id)

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
    task = assert_project_task_access(task_id, user, db)
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


# ── POST /api/project-tasks/{id}/comments ────────────────────────────────────

@task_router.post("/{task_id}/comments", status_code=201)
def add_task_comment(
    task_id: int,
    payload: TaskCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = assert_project_task_access(task_id, user, db)
    project = db.query(Project).filter(Project.id == task.project_id).first()
    _assert_customer_project_member(project, user, db)
    # Customers can only comment on client-visible tasks, never internal
    if user.role == "customer":
        if not task.is_client_visible:
            raise HTTPException(status_code=404, detail="Task not found")
        if payload.is_internal:
            raise HTTPException(status_code=403, detail="Customers cannot post internal comments")

    comment = TaskComment(
        task_id=task_id,
        author_id=user.id,
        content=payload.content,
        is_internal=payload.is_internal,
    )
    db.add(comment)
    db.add(TaskActivity(task_id=task_id, actor_id=user.id, action="comment_added"))
    db.commit()
    db.refresh(comment)

    author = db.query(User).filter(User.id == user.id).first()
    return {
        "id": comment.id,
        "task_id": comment.task_id,
        "author_id": comment.author_id,
        "author_name": author.full_name if author else None,
        "content": comment.content,
        "is_internal": comment.is_internal,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }


# ── GET /api/project-tasks/{id}/comments ─────────────────────────────────────

@task_router.get("/{task_id}/comments")
def list_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = assert_project_task_access(task_id, user, db)
    project = db.query(Project).filter(Project.id == task.project_id).first()
    _assert_customer_project_member(project, user, db)
    if user.role == "customer" and not task.is_client_visible:
        raise HTTPException(status_code=404, detail="Task not found")

    query = db.query(TaskComment).filter(TaskComment.task_id == task_id)
    if user.role == "customer":
        query = query.filter(TaskComment.is_internal == False)  # noqa: E712
    comments_raw = query.order_by(TaskComment.created_at.asc()).all()

    author_ids = {c.author_id for c in comments_raw if c.author_id}
    authors = {u.id: u for u in db.query(User).filter(User.id.in_(author_ids)).all()} if author_ids else {}
    return [
        {
            "id": c.id,
            "task_id": c.task_id,
            "author_id": c.author_id,
            "author_name": authors.get(c.author_id, None) and authors[c.author_id].full_name,
            "content": c.content,
            "is_internal": c.is_internal,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in comments_raw
    ]


# ── GET /api/project-tasks/{id}/activities ────────────────────────────────────

@task_router.get("/{task_id}/activities")
def list_task_activities(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = assert_project_task_access(task_id, user, db)
    project = db.query(Project).filter(Project.id == task.project_id).first()
    _assert_customer_project_member(project, user, db)
    if user.role == "customer" and not task.is_client_visible:
        raise HTTPException(status_code=404, detail="Task not found")

    activities_raw = (
        db.query(TaskActivity).filter(TaskActivity.task_id == task_id)
        .order_by(TaskActivity.created_at.asc()).all()
    )
    actor_ids = {a.actor_id for a in activities_raw if a.actor_id}
    actors = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}
    return [
        {
            "id": a.id,
            "task_id": a.task_id,
            "actor_id": a.actor_id,
            "actor_name": actors.get(a.actor_id, None) and actors[a.actor_id].full_name,
            "action": a.action,
            "from_value": a.from_value,
            "to_value": a.to_value,
            "detail": a.detail,
            "created_at": a.created_at,
        }
        for a in activities_raw
    ]


# ── GET/POST /api/projects/{id}/discussion ────────────────────────────────────

@router.get("/{project_id}/discussion")
def get_project_discussion(
    project_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return merged timeline of all ticket replies across tickets linked to this project."""
    from app.models.ticket import Ticket, TicketReply

    project = assert_project_access(project_id, user, db)

    ticket_query = db.query(Ticket).filter(
        Ticket.project_id == project.id,
        Ticket.is_deleted == False,  # noqa: E712
    )
    ticket_query = scope_tickets(ticket_query, user, db)
    tickets = ticket_query.all()

    if not tickets:
        return {"total": 0, "items": []}

    ticket_ids = [t.id for t in tickets]
    ticket_map = {t.id: t for t in tickets}

    reply_query = db.query(TicketReply).filter(TicketReply.ticket_id.in_(ticket_ids))
    if user.role == "customer":
        reply_query = reply_query.filter(TicketReply.is_internal == False)  # noqa: E712

    total = reply_query.count()
    replies = (
        reply_query
        .order_by(TicketReply.created_at.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    author_ids = {r.author_id for r in replies if r.author_id}
    authors = {u.id: u for u in db.query(User).filter(User.id.in_(author_ids)).all()} if author_ids else {}

    def _discussion_author_name(r, author):
        if author and author.full_name:
            return author.full_name
        email = r.author_email or (author.email if author else None)
        if email:
            return email.split("@")[0]
        return ""

    items = []
    for r in replies:
        ticket = ticket_map.get(r.ticket_id)
        author = authors.get(r.author_id) if r.author_id else None
        items.append({
            "id": r.id,
            "ticket_id": r.ticket_id,
            "ticket_subject": ticket.subject if ticket else None,
            "ticket_status": ticket.status if ticket else None,
            "author_id": r.author_id,
            "author_name": _discussion_author_name(r, author),
            "author_email": r.author_email or (author.email if author else None),
            "author_role": author.role if author else None,
            "content": r.content,
            "is_internal": r.is_internal,
            "source": r.source,
            "created_at": r.created_at,
        })

    return {"total": total, "items": items}


@router.post("/{project_id}/discussion", status_code=201)
def post_project_discussion(
    project_id: int,
    payload: ProjectDiscussionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Post a reply to the primary open ticket linked to this project."""
    from app.models.ticket import Ticket, TicketReply

    project = assert_project_access(project_id, user, db)

    ticket_query = db.query(Ticket).filter(
        Ticket.project_id == project.id,
        Ticket.is_deleted == False,  # noqa: E712
        ~Ticket.status.in_(["Closed", "Resolved"]),
    )
    ticket_query = scope_tickets(ticket_query, user, db)
    primary_ticket = ticket_query.order_by(Ticket.created_at.asc()).first()

    if not primary_ticket:
        raise HTTPException(
            status_code=409,
            detail="No open ticket linked to this project. Create or link a ticket first.",
        )

    is_internal = payload.is_internal if user.role != "customer" else False

    reply = TicketReply(
        ticket_id=primary_ticket.id,
        author_id=user.id,
        content=payload.content,
        is_internal=is_internal,
        source="portal",
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)

    author = db.query(User).filter(User.id == user.id).first()
    return {
        "id": reply.id,
        "ticket_id": reply.ticket_id,
        "ticket_subject": primary_ticket.subject,
        "ticket_status": primary_ticket.status,
        "author_id": reply.author_id,
        "author_name": author.full_name if author else None,
        "author_email": reply.author_email or (author.email if author else None),
        "author_role": author.role if author else None,
        "content": reply.content,
        "is_internal": reply.is_internal,
        "source": reply.source,
        "created_at": reply.created_at,
    }


# ── POST /api/project-tasks/{id}/approval ────────────────────────────────────

def _notify_users(db, user_ids: list[int], title: str, content: str) -> None:
    """Batch-create notifications; skip duplicates."""
    from app.services.notify import create_notification
    seen: set[int] = set()
    for uid in user_ids:
        if uid and uid not in seen:
            seen.add(uid)
            create_notification(db, uid, title=title, content=content, type="info")


def _get_project_customer_ids(db, project_id: int) -> list[int]:
    """Return user IDs of customers linked to this project (members + ticket raised_by)."""
    from app.models.ticket import Ticket
    member_ids = [
        row[0] for row in
        db.query(ProjectMember.user_id)
        .filter(ProjectMember.project_id == project_id, ProjectMember.role == "customer")
        .all()
    ]
    ticket_raised_by = [
        row[0] for row in
        db.query(Ticket.raised_by)
        .filter(
            Ticket.project_id == project_id,
            Ticket.raised_by != None,  # noqa: E711
            Ticket.is_deleted == False,  # noqa: E712
        )
        .all()
    ]
    # Union, deduplicated
    return list({uid for uid in (member_ids + ticket_raised_by) if uid})


def _get_project_staff_ids(db, project_id: int, task: ProjectTask) -> list[int]:
    """Return user IDs of staff assigned to or managing this task/project."""
    assignee_ids = [
        row[0] for row in
        db.query(TaskAssignee.user_id)
        .filter(TaskAssignee.task_id == task.id)
        .all()
    ]
    if task.assignee_id:
        assignee_ids.append(task.assignee_id)
    member_ids = [
        row[0] for row in
        db.query(ProjectMember.user_id)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.role.in_(["staff", "manager"]),
        )
        .all()
    ]
    return list({uid for uid in (assignee_ids + member_ids) if uid})


@task_router.post("/{task_id}/approval", status_code=201)
def submit_task_approval(
    task_id: int,
    payload: TaskApprovalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit, approve, or request changes on a task approval."""
    # Access control: customers see only client_visible tasks; staff/admin use normal scoping
    if user.role == "customer":
        task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        # Verify customer's org matches project org
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project or project.org_id != user.org_id or project.visibility != "customer_visible":
            raise HTTPException(status_code=404, detail="Task not found")
        if not task.is_client_visible:
            raise HTTPException(status_code=404, detail="Task not found")
        # Customer must be an explicit ProjectMember — org membership alone is not enough
        is_member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        ).first()
        if not is_member:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        task = assert_project_task_access(task_id, user, db)

    action = payload.action

    # Permission checks
    if action == "submitted_for_review":
        if user.role == "customer":
            raise HTTPException(status_code=403, detail="Customers cannot submit tasks for review")
        if task.status not in ("working", "review"):
            raise HTTPException(status_code=422, detail=f"Task must be 'working' or 'review' to submit for review, got '{task.status}'")

    elif action in ("approved", "changes_requested"):
        if user.role == "staff":
            raise HTTPException(status_code=403, detail="Staff cannot approve or request changes; only customers or admins")
        if task.status != "review":
            raise HTTPException(status_code=422, detail=f"Task must be 'review' to approve or request changes, got '{task.status}'")

    # Record old status for activity log
    old_status = task.status

    # Apply status transition
    if action == "submitted_for_review":
        task.status = "review"
    elif action == "approved":
        task.status = "approved"
    elif action == "changes_requested":
        task.status = "working"

    db.flush()

    # Create TaskApproval record
    approval = TaskApproval(
        task_id=task.id,
        action=action,
        actor_id=user.id,
        comment=payload.comment,
    )
    db.add(approval)

    # Log TaskActivity
    activity_detail = payload.comment if action == "changes_requested" else None
    db.add(TaskActivity(
        task_id=task.id,
        actor_id=user.id,
        action=action,
        from_value=old_status,
        to_value=task.status,
        detail=activity_detail,
    ))

    # Notifications
    if action == "submitted_for_review":
        customer_ids = _get_project_customer_ids(db, task.project_id)
        _notify_users(
            db, customer_ids,
            title="Task needs your approval",
            content=f'Task "{task.title}" is ready for review',
        )
    else:
        staff_ids = _get_project_staff_ids(db, task.project_id, task)
        notif_title = "Task approved" if action == "approved" else "Changes requested on task"
        notif_content = (
            f'Customer approved task "{task.title}"'
            if action == "approved"
            else f'Changes were requested on task "{task.title}"'
            + (f': {payload.comment}' if payload.comment else '')
        )
        _notify_users(db, staff_ids, title=notif_title, content=notif_content)

    db.commit()
    db.refresh(approval)

    actor = db.query(User).filter(User.id == user.id).first()
    return {
        "id": approval.id,
        "task_id": approval.task_id,
        "action": approval.action,
        "actor_id": approval.actor_id,
        "actor_name": actor.full_name if actor else None,
        "comment": approval.comment,
        "created_at": approval.created_at,
    }


# ── GET /api/project-tasks/{id}/approvals ────────────────────────────────────

@task_router.get("/{task_id}/approvals")
def list_task_approvals(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List approval history for a task, newest first."""
    if user.role == "customer":
        task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project or project.org_id != user.org_id or project.visibility != "customer_visible":
            raise HTTPException(status_code=404, detail="Task not found")
        if not task.is_client_visible:
            raise HTTPException(status_code=404, detail="Task not found")
        is_member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        ).first()
        if not is_member:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        task = assert_project_task_access(task_id, user, db)

    approvals = (
        db.query(TaskApproval)
        .filter(TaskApproval.task_id == task_id)
        .order_by(TaskApproval.created_at.desc(), TaskApproval.id.desc())
        .all()
    )

    actor_ids = {a.actor_id for a in approvals if a.actor_id}
    actors = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}

    return [
        {
            "id": a.id,
            "task_id": a.task_id,
            "action": a.action,
            "actor_id": a.actor_id,
            "actor_name": actors[a.actor_id].full_name if a.actor_id in actors else None,
            "comment": a.comment,
            "created_at": a.created_at,
        }
        for a in approvals
    ]
