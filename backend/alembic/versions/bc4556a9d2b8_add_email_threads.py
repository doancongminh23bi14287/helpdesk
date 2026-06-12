"""add_email_threads

Revision ID: bc4556a9d2b8
Revises: 01f1d11e5977
Create Date: 2026-06-05 22:11:41.104826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc4556a9d2b8'
down_revision: Union[str, None] = '01f1d11e5977'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_threads',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.String(length=500), nullable=True),
        sa.Column('in_reply_to', sa.String(length=500), nullable=True),
        sa.Column('references', sa.String(length=2000), nullable=True),
        sa.Column('direction', sa.Enum('inbound', 'outbound'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_threads_in_reply_to'), 'email_threads', ['in_reply_to'], unique=False)
    op.create_index(op.f('ix_email_threads_message_id'), 'email_threads', ['message_id'], unique=False)
    op.create_index(op.f('ix_email_threads_ticket_id'), 'email_threads', ['ticket_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_email_threads_ticket_id'), table_name='email_threads')
    op.drop_index(op.f('ix_email_threads_message_id'), table_name='email_threads')
    op.drop_index(op.f('ix_email_threads_in_reply_to'), table_name='email_threads')
    op.drop_table('email_threads')
