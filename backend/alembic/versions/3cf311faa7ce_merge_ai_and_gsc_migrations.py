"""merge ai and gsc migrations

Revision ID: 3cf311faa7ce
Revises: 20260624_add_ai_tables, efbee4865219
Create Date: 2026-06-25 10:48:29.670851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3cf311faa7ce'
down_revision: Union[str, None] = ('20260624_add_ai_tables', 'efbee4865219')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
