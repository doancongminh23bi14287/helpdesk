"""add_password_reset_otp

Revision ID: 8e0d75fd3d32
Revises: 9b283db56bda
Create Date: 2026-06-13 22:12:41.662095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e0d75fd3d32'
down_revision: Union[str, None] = '9b283db56bda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('password_reset_otps',
    sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('otp_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_otps_user_id'), 'password_reset_otps', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('password_reset_otps')
