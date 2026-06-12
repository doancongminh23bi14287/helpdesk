"""add_user_avatar_fields

Revision ID: 20260611_user_avatar
Revises: 20260608_projects_tasks
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260611_user_avatar"
down_revision: Union[str, None] = "20260608_projects_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("avatar_path", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("avatar_mime_type", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("avatar_size_bytes", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("avatar_updated_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("avatar_color", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_color")
    op.drop_column("users", "avatar_updated_at")
    op.drop_column("users", "avatar_size_bytes")
    op.drop_column("users", "avatar_mime_type")
    op.drop_column("users", "avatar_path")
    op.drop_column("users", "avatar_url")
