"""add_sla_paused_total_seconds

Revision ID: 02b8c41c562f
Revises: 0012
Create Date: 2026-06-05 21:54:42.881179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02b8c41c562f'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tickets',
        sa.Column('sla_paused_total_seconds', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('tickets', 'sla_paused_total_seconds')
