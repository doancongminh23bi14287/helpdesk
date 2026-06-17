"""add_user_sessions

Revision ID: d822bc63c2a2
Revises: 1d6dde1ad7fe
Create Date: 2026-06-06 23:55:11.000225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd822bc63c2a2'
down_revision: Union[str, None] = '1d6dde1ad7fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_sessions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
    sa.Column('current_jti', sa.String(length=36), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_engine='InnoDB',
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(op.f('ix_user_sessions_refresh_token_hash'), 'user_sessions', ['refresh_token_hash'], unique=True)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('user_sessions')
