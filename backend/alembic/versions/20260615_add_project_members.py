"""add_project_members_table

Revision ID: 20260615_add_project_members
Revises: 20260615_ticket_type_enum
Create Date: 2026-06-15 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_add_project_members"
down_revision: Union[str, None] = "20260615_ticket_type_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("manager", "staff", "customer"),
            nullable=False,
        ),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        op.f("ix_project_members_project_id"), "project_members", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_members_user_id"), "project_members", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("project_members")
