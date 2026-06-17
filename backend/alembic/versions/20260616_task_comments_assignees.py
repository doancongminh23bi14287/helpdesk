"""add_task_comments_activities_assignees_and_ticket_task_id

Revision ID: 20260616_task_comments_assignees
Revises: 20260615_project_doc_source
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260616_task_comments_assignees"
down_revision: Union[str, None] = "20260615_project_doc_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # task_comments
    op.create_table(
        "task_comments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id"])

    # task_activities
    op.create_table(
        "task_activities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("from_value", sa.String(255), nullable=True),
        sa.Column("to_value", sa.String(255), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_task_activities_task_id", "task_activities", ["task_id"])

    # task_assignees
    op.create_table(
        "task_assignees",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("assigned_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_assignees_task_user"),
    )
    op.create_index("ix_task_assignees_task_id", "task_assignees", ["task_id"])
    op.create_index("ix_task_assignees_user_id", "task_assignees", ["user_id"])

    # tickets.task_id
    op.add_column(
        "tickets",
        sa.Column(
            "task_id",
            sa.BigInteger(),
            sa.ForeignKey("project_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Backfill task_assignees from project_tasks.assignee_id
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT id, assignee_id FROM project_tasks WHERE assignee_id IS NOT NULL")
    )
    rows = result.fetchall()
    if rows:
        conn.execute(
            sa.text(
                "INSERT INTO task_assignees (task_id, user_id, is_primary, created_at) "
                "VALUES (:tid, :uid, 1, NOW())"
            ),
            [{"tid": r[0], "uid": r[1]} for r in rows],
        )
    print(f"Backfilling {len(rows)} rows into task_assignees")


def downgrade() -> None:
    # Drop tickets.task_id FK constraint before dropping the column
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE"
        " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tickets'"
        " AND COLUMN_NAME = 'task_id' AND REFERENCED_TABLE_NAME = 'project_tasks'"
    ))
    row = result.fetchone()
    if row:
        op.drop_constraint(row[0], "tickets", type_="foreignkey")
    op.drop_column("tickets", "task_id")
    op.drop_table("task_assignees")
    op.drop_table("task_activities")
    op.drop_table("task_comments")
