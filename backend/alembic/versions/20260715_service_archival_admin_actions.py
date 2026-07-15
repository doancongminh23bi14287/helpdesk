"""add service archival metadata and admin service actions

Revision ID: 5f7a2b4c1d9e
Revises: c8d9e0f1a2b3
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '5f7a2b4c1d9e'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('services', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('services', sa.Column('archived_at', sa.DateTime(), nullable=True))
    op.add_column('services', sa.Column('archived_by_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        'fk_services_archived_by_id_users',
        'services',
        'users',
        ['archived_by_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_services_archived_by_id_users', 'services', type_='foreignkey')
    op.drop_column('services', 'archived_by_id')
    op.drop_column('services', 'archived_at')
    op.drop_column('services', 'is_archived')
