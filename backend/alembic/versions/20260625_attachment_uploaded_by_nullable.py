"""attachment_uploaded_by_nullable

Revision ID: 20260625_attachment_uploaded_by_nullable
Revises: 3cf311faa7ce
Create Date: 2026-06-25

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260625_attachment_uploaded_by_nullable'
down_revision: Union[str, None] = '3cf311faa7ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'ticket_attachments',
        'uploaded_by',
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'ticket_attachments',
        'uploaded_by',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
