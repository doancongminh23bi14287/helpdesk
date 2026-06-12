"""add_last_assigned_at_to_users

Revision ID: 01f1d11e5977
Revises: 02b8c41c562f
Create Date: 2026-06-05 21:59:24.425207

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01f1d11e5977'
down_revision: Union[str, None] = '02b8c41c562f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_assigned_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_assigned_at')
