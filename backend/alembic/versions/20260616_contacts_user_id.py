"""add user_id to contacts

Revision ID: 20260616_contacts_user_id
Revises: 20260618_svc_type_enum
Create Date: 2026-06-16
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260616_contacts_user_id"
down_revision: Union[str, None] = "20260618_svc_type_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # MariaDB requires dropping FK constraint before the column
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE"
        " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'contacts'"
        " AND COLUMN_NAME = 'user_id' AND REFERENCED_TABLE_NAME = 'users'"
    ))
    row = result.fetchone()
    if row:
        op.drop_constraint(row[0], "contacts", type_="foreignkey")
    op.drop_column("contacts", "user_id")
