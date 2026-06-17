"""expand_services_type_enum

Revision ID: 20260618_svc_type_enum
Revises: 20260617_task_approvals
Create Date: 2026-06-18 00:00:00.000000

Add 'domain' and 'support' to services.type ENUM to match Item.type.
Safe: only adding values, never removing.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260618_svc_type_enum"
down_revision: Union[str, None] = "20260617_task_approvals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE services MODIFY COLUMN type "
        "ENUM('saas','hosting','domain','support','other') "
        "NOT NULL DEFAULT 'saas'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE services MODIFY COLUMN type "
        "ENUM('saas','hosting','other') "
        "NOT NULL DEFAULT 'saas'"
    )
