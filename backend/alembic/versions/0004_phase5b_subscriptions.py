"""phase5b subscriptions

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create subscription_plans table
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "billing_cycle",
            sa.Enum("monthly", "quarterly", "yearly", name="sub_billing_cycle"),
            nullable=False,
            server_default=sa.text("'monthly'"),
        ),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_subscription_plans_code"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_subscription_plans_item"),
    )

    # 2. Create subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("subscription_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("price_list_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "trial", "active", "past_due", "cancelled", "expired",
                name="subscription_status",
            ),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("trial_end_date", sa.Date(), nullable=True),
        sa.Column("current_period_start", sa.Date(), nullable=False),
        sa.Column("current_period_end", sa.Date(), nullable=False),
        sa.Column("next_billing_date", sa.Date(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("unit_price", sa.DECIMAL(15, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_subscriptions_org"),
        sa.ForeignKeyConstraint(
            ["subscription_plan_id"],
            ["subscription_plans.id"],
            name="fk_subscriptions_plan",
        ),
        sa.ForeignKeyConstraint(
            ["price_list_id"], ["price_lists.id"], name="fk_subscriptions_price_list"
        ),
    )

    # 3. Add subscription_id column to services and create FK
    op.add_column(
        "services",
        sa.Column("subscription_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_services_subscription",
        "services",
        "subscriptions",
        ["subscription_id"],
        ["id"],
    )


def downgrade() -> None:
    # Drop FK and column from services first
    op.drop_constraint("fk_services_subscription", "services", type_="foreignkey")
    op.drop_column("services", "subscription_id")

    # Drop tables in reverse dependency order
    op.drop_table("subscriptions")
    op.drop_table("subscription_plans")
