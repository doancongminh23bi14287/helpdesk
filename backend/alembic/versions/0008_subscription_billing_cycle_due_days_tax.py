"""add billing_cycle/due_days/end_date to subscriptions, tax_rate to plans

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # subscription_plans: add tax_rate
    op.add_column(
        "subscription_plans",
        sa.Column("tax_rate", sa.DECIMAL(5, 2), nullable=False, server_default="0.00"),
    )

    # subscriptions: add billing_cycle, due_days, end_date
    op.add_column(
        "subscriptions",
        sa.Column(
            "billing_cycle",
            sa.Enum("monthly", "quarterly", "yearly"),
            nullable=False,
            server_default=sa.text("'monthly'"),
        ),
    )
    op.add_column(
        "subscriptions",
        sa.Column("due_days", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("end_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "end_date")
    op.drop_column("subscriptions", "due_days")
    op.drop_column("subscriptions", "billing_cycle")
    op.drop_column("subscription_plans", "tax_rate")
