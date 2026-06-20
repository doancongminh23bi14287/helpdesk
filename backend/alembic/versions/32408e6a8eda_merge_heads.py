"""merge heads

Revision ID: 32408e6a8eda
Revises: 20260616_contacts_user_id, a1b2c3d4e5f6
Create Date: 2026-06-20 17:53:54.174803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32408e6a8eda'
down_revision: Union[str, None] = ('20260616_contacts_user_id', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
