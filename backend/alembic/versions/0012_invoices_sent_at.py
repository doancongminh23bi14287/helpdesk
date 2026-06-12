"""invoices: add sent_at column

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('invoices', sa.Column('sent_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('invoices', 'sent_at')
