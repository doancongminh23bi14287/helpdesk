"""add_task_approvals_table

Revision ID: 20260617_task_approvals
Revises: 20260616_task_status_approved
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260617_task_approvals"
down_revision: Union[str, None] = "20260616_task_status_approved"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_approvals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "task_id",
            sa.BigInteger(),
            sa.ForeignKey("project_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Enum("submitted_for_review", "approved", "changes_requested"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_task_approvals_task_id", "task_approvals", ["task_id"])


def downgrade() -> None:
    op.drop_table("task_approvals")  # drops FK constraints and indexes atomically
