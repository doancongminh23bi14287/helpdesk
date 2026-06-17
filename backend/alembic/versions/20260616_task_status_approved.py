"""add_approved_to_project_task_status_enum

Revision ID: 20260616_task_status_approved
Revises: 20260616_task_comments_assignees
Create Date: 2026-06-16 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260616_task_status_approved"
down_revision: Union[str, None] = "20260616_task_comments_assignees"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_ENUM = "ENUM('open','working','review','approved','completed','cancelled') NOT NULL DEFAULT 'open'"
_OLD_ENUM = "ENUM('open','working','review','completed','cancelled') NOT NULL DEFAULT 'open'"


def upgrade() -> None:
    # Single ALTER — MariaDB allows adding a new ENUM value safely without data loss
    op.get_bind().execute(sa.text(f"ALTER TABLE project_tasks MODIFY COLUMN status {_NEW_ENUM}"))


def downgrade() -> None:
    # Move any 'approved' rows back to 'review' before shrinking the enum
    op.get_bind().execute(
        sa.text("UPDATE project_tasks SET status = 'review' WHERE status = 'approved'")
    )
    op.get_bind().execute(sa.text(f"ALTER TABLE project_tasks MODIFY COLUMN status {_OLD_ENUM}"))
