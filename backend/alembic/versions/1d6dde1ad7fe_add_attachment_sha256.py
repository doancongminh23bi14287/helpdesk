"""add_attachment_sha256

Revision ID: 1d6dde1ad7fe
Revises: d182c78aceec
Create Date: 2026-06-06 22:54:33.245263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d6dde1ad7fe'
down_revision: Union[str, None] = 'd182c78aceec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ticket_attachments', sa.Column('detected_mime', sa.String(length=255), nullable=True))
    op.add_column('ticket_attachments', sa.Column('sha256', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('ticket_attachments', 'sha256')
    op.drop_column('ticket_attachments', 'detected_mime')
