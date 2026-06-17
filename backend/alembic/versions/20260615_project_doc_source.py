"""add_project_document_source_and_ticket_attachment_ref

Revision ID: 20260615_project_doc_source
Revises: 20260615_ticket_assignees
Create Date: 2026-06-15 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_project_doc_source"
down_revision: Union[str, None] = "20260615_ticket_assignees"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reference to original ticket attachment (nullable — not a duplicate, just a pointer)
    op.add_column(
        "project_documents",
        sa.Column(
            "ticket_attachment_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_project_documents_ticket_attachment",
        "project_documents",
        "ticket_attachments",
        ["ticket_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Source: how this document arrived in the project
    op.add_column(
        "project_documents",
        sa.Column(
            "source",
            sa.Enum("upload", "ticket_attachment"),
            nullable=False,
            server_default="upload",
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_project_documents_ticket_attachment",
        "project_documents",
        type_="foreignkey",
    )
    op.drop_column("project_documents", "ticket_attachment_id")
    op.drop_column("project_documents", "source")
