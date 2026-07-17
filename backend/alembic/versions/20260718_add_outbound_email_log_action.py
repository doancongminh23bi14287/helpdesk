"""allow outbound email log entries

Revision ID: d1c8e4f2a7b9
Revises: 9a6c4d2e7f10
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "d1c8e4f2a7b9"
down_revision: Union[str, None] = "9a6c4d2e7f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("email_log"):
        return

    column_type = bind.execute(
        sa.text(
            "SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'email_log' AND COLUMN_NAME = 'action'"
        )
    ).scalar()
    if column_type and "'outbound'" in column_type:
        return

    op.execute(
        "ALTER TABLE email_log MODIFY action "
        "ENUM('created', 'appended', 'skipped', 'error', 'outbound') NOT NULL"
    )


def downgrade() -> None:
    # Downgrading would discard outbound log records, so leave the schema intact.
    pass
