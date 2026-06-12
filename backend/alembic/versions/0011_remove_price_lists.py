"""remove price_lists and price_list_items tables, drop price_list_id columns

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop price_list_id FK + column from subscriptions
    op.drop_constraint("fk_subscriptions_price_list", "subscriptions", type_="foreignkey")
    op.drop_column("subscriptions", "price_list_id")

    # Drop price_list_id FK + column from organizations (use_alter FK)
    op.drop_constraint("fk_organizations_price_list", "organizations", type_="foreignkey")
    op.drop_column("organizations", "price_list_id")

    # Drop subscription_plans price_list_id if present (may not exist)
    # Drop dependent table first, then price_lists
    op.drop_table("price_list_items")
    op.drop_table("price_lists")


def downgrade() -> None:
    op.create_table(
        "price_lists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="VND"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "price_list_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("price_list_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_price", sa.DECIMAL(15, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["price_list_id"], ["price_lists.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
    )
    op.add_column("organizations", sa.Column("price_list_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_organizations_price_list", "organizations", "price_lists", ["price_list_id"], ["id"])
    op.add_column("subscriptions", sa.Column("price_list_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_subscriptions_price_list", "subscriptions", "price_lists", ["price_list_id"], ["id"])
