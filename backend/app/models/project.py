from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, DECIMAL, Enum, ForeignKey, String, Text
from sqlalchemy.sql import func

from app.database import Base


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
        Enum("open", "working", "review", "completed", "cancelled"),
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
