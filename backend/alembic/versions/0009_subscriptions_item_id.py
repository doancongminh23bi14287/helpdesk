"""make subscription_plan_id nullable, add item_id FK to subscriptions

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make subscription_plan_id nullable (items-based subscriptions have no plan)
    op.alter_column(
        "subscriptions", "subscription_plan_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    # Add item_id FK — the "plan" source for new subscriptions
    op.add_column(
        "subscriptions",
        sa.Column("item_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_subscriptions_item", "subscriptions", "items",
        ["item_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_subscriptions_item", "subscriptions", type_="foreignkey")
    op.drop_column("subscriptions", "item_id")
    op.alter_column(
        "subscriptions", "subscription_plan_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
