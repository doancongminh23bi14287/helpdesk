"""add_invoice_cancel_reason

Revision ID: d182c78aceec
Revises: ff73e7de64fc
Create Date: 2026-06-06 22:22:46.556676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd182c78aceec'
down_revision: Union[str, None] = 'ff73e7de64fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('invoices', sa.Column('cancel_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('invoices', 'cancel_reason')
