"""add_invoice_payments

Revision ID: ff73e7de64fc
Revises: d8e7ed81518b
Create Date: 2026-06-05 22:50:45.985861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff73e7de64fc'
down_revision: Union[str, None] = 'd8e7ed81518b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'invoice_payments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('invoice_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('reference', sa.String(length=255), nullable=True),
        sa.Column('paid_by', sa.BigInteger(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['paid_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_invoice_payments_invoice_id'),
        'invoice_payments', ['invoice_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_table('invoice_payments')
