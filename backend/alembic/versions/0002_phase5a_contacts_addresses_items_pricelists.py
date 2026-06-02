"""phase5a contacts addresses items pricelists

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create items table (needed before price_lists references are made,
    #    and before price_list_items references items)
    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "type",
            sa.Enum("saas", "hosting", "domain", "support", "other", name="item_type"),
            nullable=False,
        ),
        sa.Column("unit_price", sa.DECIMAL(15, 2), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False, server_default="month"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_items_code"),
    )

    # 2. Create price_lists table
    op.create_table(
        "price_lists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="VND"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Create price_list_items table
    op.create_table(
        "price_list_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("price_list_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_price", sa.DECIMAL(15, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["price_list_id"], ["price_lists.id"], name="fk_pli_price_list"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_pli_item"),
        sa.UniqueConstraint("price_list_id", "item_id", name="uq_pli"),
    )

    # 4. Create contacts table
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column(
            "role",
            sa.Enum("primary", "billing", "technical", "other", name="contact_role"),
            nullable=False,
            server_default="primary",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_contacts_org"),
    )

    # 5. Create addresses table
    op.create_table(
        "addresses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("province", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=False, server_default="Vietnam"),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_addresses_org"),
    )

    # 6. Alter organizations — add price_list_id FK column
    op.add_column(
        "organizations",
        sa.Column("price_list_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizations_price_list",
        "organizations",
        "price_lists",
        ["price_list_id"],
        ["id"],
    )


def downgrade() -> None:
    # Drop FK and column from organizations first
    op.drop_constraint("fk_organizations_price_list", "organizations", type_="foreignkey")
    op.drop_column("organizations", "price_list_id")

    # Drop tables in reverse dependency order
    op.drop_table("addresses")
    op.drop_table("contacts")
    op.drop_table("price_list_items")
    op.drop_table("price_lists")
    op.drop_table("items")
