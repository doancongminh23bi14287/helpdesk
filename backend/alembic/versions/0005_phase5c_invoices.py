"""phase5c invoices

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create invoice_number_seq table
    op.create_table(
        "invoice_number_seq",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("year"),
    )

    # 2. Create invoices table
    op.create_table(
        "invoices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("subscription_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "sent", "paid", "overdue", "cancelled", name="invoice_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("subtotal", sa.DECIMAL(15, 2), nullable=False),
        sa.Column(
            "tax_rate",
            sa.DECIMAL(5, 2),
            nullable=False,
            server_default=sa.text("'10.00'"),
        ),
        sa.Column("tax_amount", sa.DECIMAL(15, 2), nullable=False),
        sa.Column("total", sa.DECIMAL(15, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
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
        sa.UniqueConstraint("invoice_number", name="uq_invoices_invoice_number"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_invoices_org"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["subscriptions.id"], name="fk_invoices_subscription"
        ),
    )

    # 3. Create invoice_lines table
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column(
            "quantity",
            sa.DECIMAL(10, 2),
            nullable=False,
            server_default=sa.text("'1.00'"),
        ),
        sa.Column("unit_price", sa.DECIMAL(15, 2), nullable=False),
        sa.Column("line_total", sa.DECIMAL(15, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_invoice_lines_invoice",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_invoice_lines_item"),
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("invoice_number_seq")
