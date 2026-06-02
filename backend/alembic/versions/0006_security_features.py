"""security features: login_history + must_change_password

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add must_change_password to users table
    op.add_column("users", sa.Column(
        "must_change_password",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("0"),
    ))

    # Create login_history table
    op.create_table(
        "login_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("success", "failed", "blocked", name="login_status"),
            nullable=False,
            server_default="success",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_login_history_user_id", "login_history", ["user_id"])
    op.create_index("ix_login_history_created_at", "login_history", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_login_history_created_at", "login_history")
    op.drop_index("ix_login_history_user_id", "login_history")
    op.drop_table("login_history")
    op.execute("DROP TYPE IF EXISTS login_status")
    op.drop_column("users", "must_change_password")
