"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # Schema already applied via SCHEMA.sql docker-entrypoint init


def downgrade() -> None:
    pass
