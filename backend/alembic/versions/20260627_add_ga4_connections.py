"""add_ga4_connections

Revision ID: b2c3d4e5f6a7
Revises: a9b8c7d6e5f4
Create Date: 2026-06-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ga4_connections',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('org_id', sa.BigInteger(), nullable=False),
        sa.Column('property_id', sa.String(50), nullable=True),
        sa.Column('property_name', sa.String(255), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(), nullable=True),
        sa.Column('connected_by', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='connected'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'), onupdate=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['connected_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', name='uq_ga4_connections_org_id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )
    op.create_index('ix_ga4_connections_org_id', 'ga4_connections', ['org_id'])


def downgrade() -> None:
    op.drop_index('ix_ga4_connections_org_id', table_name='ga4_connections')
    op.drop_table('ga4_connections')
