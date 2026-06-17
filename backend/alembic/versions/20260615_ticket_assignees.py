"""add_ticket_assignees_and_assignment_mode

Revision ID: 20260615_ticket_assignees
Revises: 20260615_add_project_members
Create Date: 2026-06-15 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_ticket_assignees"
down_revision: Union[str, None] = "20260615_add_project_members"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ticket_assignees join table
    op.create_table(
        "ticket_assignees",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("assigned_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "user_id", name="uq_ticket_assignees_ticket_user"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_ticket_assignees_ticket_id", "ticket_assignees", ["ticket_id"])
    op.create_index("ix_ticket_assignees_user_id", "ticket_assignees", ["user_id"])

    # 2. Backfill: copy every tickets.assignee_id IS NOT NULL → ticket_assignees (is_primary=True)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT id, assignee_id FROM tickets WHERE assignee_id IS NOT NULL"
    ))
    rows = result.fetchall()
    print(f"\n[Migration] Backfilling {len(rows)} rows into ticket_assignees from tickets.assignee_id")
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO ticket_assignees (ticket_id, user_id, is_primary, created_at) "
                "VALUES (:tid, :uid, 1, NOW())"
            ),
            {"tid": row[0], "uid": row[1]},
        )

    # 3. Add assignment_mode column to tickets (default 'auto' for all existing rows)
    op.add_column(
        "tickets",
        sa.Column(
            "assignment_mode",
            sa.Enum("none", "auto", "manual"),
            nullable=False,
            server_default="auto",
        ),
    )


def downgrade() -> None:
    op.drop_column("tickets", "assignment_mode")
    op.drop_table("ticket_assignees")
