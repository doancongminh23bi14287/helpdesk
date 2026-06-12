"""add_project_documents

Revision ID: 20260611_project_documents
Revises: 20260611_user_avatar
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260611_project_documents"
down_revision: Union[str, None] = "20260611_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("detected_mime", sa.String(length=255), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("is_client_visible", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(op.f("ix_project_documents_project_id"), "project_documents", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_documents_is_client_visible"), "project_documents", ["is_client_visible"], unique=False)
    op.create_index(op.f("ix_project_documents_uploaded_by"), "project_documents", ["uploaded_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_documents_uploaded_by"), table_name="project_documents")
    op.drop_index(op.f("ix_project_documents_is_client_visible"), table_name="project_documents")
    op.drop_index(op.f("ix_project_documents_project_id"), table_name="project_documents")
    op.drop_table("project_documents")
