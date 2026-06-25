"""add_ai_tables

Revision ID: 20260624_add_ai_tables
Revises: 32408e6a8eda
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260624_add_ai_tables'
down_revision: Union[str, None] = '32408e6a8eda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ticket_ai_predictions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.BigInteger(), nullable=False),
        sa.Column('predicted_category', sa.String(length=100), nullable=False),
        sa.Column('predicted_priority', sa.String(length=50), nullable=False),
        sa.Column('predicted_department', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_ticket_ai_predictions_ticket_id'),
        'ticket_ai_predictions', ['ticket_id'], unique=False,
    )

    op.create_table(
        'ai_reply_suggestions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.BigInteger(), nullable=False),
        sa.Column('reply_id', sa.BigInteger(), nullable=True),
        sa.Column('prompt_snapshot_hash', sa.String(length=64), nullable=False),
        sa.Column('generated_text', sa.Text(), nullable=False),
        sa.Column('accepted', sa.Boolean(), nullable=False),
        sa.Column('edited', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reply_id'], ['ticket_replies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_ai_reply_suggestions_ticket_id'),
        'ai_reply_suggestions', ['ticket_id'], unique=False,
    )


def downgrade() -> None:
    # Drop tables first (removes FK constraints), then indexes are gone automatically
    op.drop_table('ai_reply_suggestions')
    op.drop_table('ticket_ai_predictions')
