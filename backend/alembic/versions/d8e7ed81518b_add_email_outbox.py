"""add_email_outbox

Revision ID: d8e7ed81518b
Revises: bc4556a9d2b8
Create Date: 2026-06-05 22:32:03.042922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e7ed81518b'
down_revision: Union[str, None] = 'bc4556a9d2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_outbox',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('email_type', sa.String(length=50), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('recipient_name', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('related_type', sa.String(length=50), nullable=True),
        sa.Column('related_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('email_outbox')
