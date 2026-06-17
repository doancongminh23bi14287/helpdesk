from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, DECIMAL, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class TaskActivity(Base):
    __tablename__ = "task_activities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    from_value = Column(String(255), nullable=True)
    to_value = Column(String(255), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TaskApproval(Base):
    __tablename__ = "task_approvals"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    action = Column(
        Enum("submitted_for_review", "approved", "changes_requested"),
        nullable=False,
    )
    actor_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TaskAssignee(Base):
    __tablename__ = "task_assignees"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_assignees_task_user"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False, server_default="0")
    assigned_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    service_id = Column(BigInteger, ForeignKey("services.id"), nullable=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(
        Enum("seo", "website", "hosting", "maintenance", "other"),
        nullable=False,
        default="seo",
        server_default="seo",
    )
    status = Column(
        Enum("open", "working", "on_hold", "completed", "cancelled"),
        nullable=False,
        default="open",
        server_default="open",
    )
    visibility = Column(
        Enum("internal", "customer_visible"),
        nullable=False,
        default="customer_visible",
        server_default="customer_visible",
    )
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    progress_percent = Column(DECIMAL(5, 2), nullable=False, default=0, server_default="0.00")
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    project_manager_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    members = relationship(
        "ProjectMember",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(
        Enum(
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
        ),
        nullable=False,
        default="other",
        server_default="other",
    )
    assignee_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    status = Column(
        Enum("open", "working", "review", "approved", "completed", "cancelled"),
        nullable=False,
        default="open",
        server_default="open",
    )
    priority = Column(
        Enum("low", "medium", "high", "urgent"),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    is_client_visible = Column(Boolean, nullable=False, default=False, server_default="0")
    internal_note = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    comments = relationship("TaskComment", foreign_keys="TaskComment.task_id", cascade="all, delete-orphan")
    activities = relationship("TaskActivity", foreign_keys="TaskActivity.task_id", cascade="all, delete-orphan")
    task_assignees = relationship("TaskAssignee", foreign_keys="TaskAssignee.task_id", cascade="all, delete-orphan")
    approvals = relationship("TaskApproval", foreign_keys="TaskApproval.task_id", cascade="all, delete-orphan")


class ProjectDocument(Base):
    __tablename__ = "project_documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    detected_mime = Column(String(255), nullable=True)
    sha256 = Column(String(64), nullable=True)
    is_client_visible = Column(Boolean, nullable=False, default=False, server_default="0")
    uploaded_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    ticket_attachment_id = Column(BigInteger, ForeignKey("ticket_attachments.id", ondelete="SET NULL"), nullable=True)
    source = Column(Enum("upload", "ticket_attachment"), nullable=False, default="upload", server_default="upload")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum("manager", "staff", "customer"), nullable=False)
    added_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
