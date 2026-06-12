"""add tax_rate to subscriptions

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("tax_rate", sa.DECIMAL(5, 2), nullable=False, server_default="0.00"),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "tax_rate")
