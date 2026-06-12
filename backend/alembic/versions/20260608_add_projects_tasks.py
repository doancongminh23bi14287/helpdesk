"""add_projects_tasks

Revision ID: 20260608_projects_tasks
Revises: d822bc63c2a2
Create Date: 2026-06-08 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260608_projects_tasks"
down_revision: Union[str, None] = "d822bc63c2a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=True),
        sa.Column("subscription_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_type", sa.Enum("seo", "website", "hosting", "maintenance", "other"), server_default="seo", nullable=False),
        sa.Column("status", sa.Enum("open", "working", "on_hold", "completed", "cancelled"), server_default="open", nullable=False),
        sa.Column("visibility", sa.Enum("internal", "customer_visible"), server_default="customer_visible", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("progress_percent", sa.Numeric(precision=5, scale=2), server_default="0.00", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("project_manager_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_manager_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(op.f("ix_projects_org_id"), "projects", ["org_id"], unique=False)
    op.create_index(op.f("ix_projects_service_id"), "projects", ["service_id"], unique=False)
    op.create_index(op.f("ix_projects_subscription_id"), "projects", ["subscription_id"], unique=False)
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)
    op.create_index(op.f("ix_projects_project_type"), "projects", ["project_type"], unique=False)
    op.create_index(op.f("ix_projects_due_date"), "projects", ["due_date"], unique=False)
    op.create_index(op.f("ix_projects_project_manager_id"), "projects", ["project_manager_id"], unique=False)

    op.create_table(
        "project_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "task_type",
            sa.Enum(
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
            server_default="other",
            nullable=False,
        ),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Enum("open", "working", "review", "completed", "cancelled"), server_default="open", nullable=False),
        sa.Column("priority", sa.Enum("low", "medium", "high", "urgent"), server_default="medium", nullable=False),
        sa.Column("is_client_visible", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(op.f("ix_project_tasks_project_id"), "project_tasks", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_tasks_assignee_id"), "project_tasks", ["assignee_id"], unique=False)
    op.create_index(op.f("ix_project_tasks_status"), "project_tasks", ["status"], unique=False)
    op.create_index(op.f("ix_project_tasks_priority"), "project_tasks", ["priority"], unique=False)
    op.create_index(op.f("ix_project_tasks_due_date"), "project_tasks", ["due_date"], unique=False)
    op.create_index(op.f("ix_project_tasks_is_client_visible"), "project_tasks", ["is_client_visible"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_tasks_is_client_visible"), table_name="project_tasks")
    op.drop_index(op.f("ix_project_tasks_due_date"), table_name="project_tasks")
    op.drop_index(op.f("ix_project_tasks_priority"), table_name="project_tasks")
    op.drop_index(op.f("ix_project_tasks_status"), table_name="project_tasks")
    op.drop_index(op.f("ix_project_tasks_assignee_id"), table_name="project_tasks")
    op.drop_index(op.f("ix_project_tasks_project_id"), table_name="project_tasks")
    op.drop_table("project_tasks")
    op.drop_index(op.f("ix_projects_project_manager_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_due_date"), table_name="projects")
    op.drop_index(op.f("ix_projects_project_type"), table_name="projects")
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_index(op.f("ix_projects_subscription_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_service_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_org_id"), table_name="projects")
    op.drop_table("projects")
