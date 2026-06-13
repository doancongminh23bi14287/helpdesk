"""add_ticket_project_id

Revision ID: 9b283db56bda
Revises: 20260611_project_documents
Create Date: 2026-06-13 19:59:17.570951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b283db56bda'
down_revision: Union[str, None] = '20260611_project_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tickets', sa.Column('project_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(None, 'tickets', 'projects', ['project_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'tickets', type_='foreignkey')
    op.drop_column('tickets', 'project_id')
