"""add ticket transfer requests

Revision ID: 9a6c4d2e7f10
Revises: 5f7a2b4c1d9e
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "9a6c4d2e7f10"
down_revision: Union[str, None] = "5f7a2b4c1d9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("ticket_transfer_requests"):
        return

    op.create_table(
        "ticket_transfer_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("from_staff_id", sa.BigInteger(), nullable=False),
        sa.Column("to_staff_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "declined", name="ticket_transfer_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_transfer_requests_ticket_id_tickets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_staff_id"],
            ["users.id"],
            name="fk_ticket_transfer_requests_from_staff_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["to_staff_id"],
            ["users.id"],
            name="fk_ticket_transfer_requests_to_staff_id_users",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_transfer_requests_ticket_id",
        "ticket_transfer_requests",
        ["ticket_id"],
    )
    op.create_index(
        "ix_ticket_transfer_requests_from_staff_id",
        "ticket_transfer_requests",
        ["from_staff_id"],
    )
    op.create_index(
        "ix_ticket_transfer_requests_to_staff_id",
        "ticket_transfer_requests",
        ["to_staff_id"],
    )
    op.create_index(
        "ix_ticket_transfer_requests_status",
        "ticket_transfer_requests",
        ["status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if inspect(bind).has_table("ticket_transfer_requests"):
        op.drop_table("ticket_transfer_requests")
