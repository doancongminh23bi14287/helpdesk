"""fix_invoice_tax_rate_default

Revision ID: 7da8810a091c
Revises: 8e0d75fd3d32
Create Date: 2026-06-14 01:43:05.339747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7da8810a091c'
down_revision: Union[str, None] = '8e0d75fd3d32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix B1: change invoice tax_rate server_default from 10.00 to 0.00
    op.alter_column('invoices', 'tax_rate', server_default='0.00',
                    existing_type=sa.DECIMAL(5, 2), existing_nullable=False)

    # Fix B5: add ON DELETE CASCADE to password_reset_otps.user_id FK
    op.drop_constraint('password_reset_otps_ibfk_1', 'password_reset_otps', type_='foreignkey')
    op.create_foreign_key(
        None, 'password_reset_otps', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    # Reverse B5: remove CASCADE from FK (find auto-generated name)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE"
        " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'password_reset_otps'"
        " AND COLUMN_NAME = 'user_id' AND REFERENCED_TABLE_NAME = 'users'"
    ))
    row = result.fetchone()
    if row:
        op.drop_constraint(row[0], 'password_reset_otps', type_='foreignkey')
    op.create_foreign_key(
        'password_reset_otps_ibfk_1', 'password_reset_otps', 'users', ['user_id'], ['id']
    )

    # Reverse B1: restore invoice tax_rate server_default to 10.00
    op.alter_column('invoices', 'tax_rate', server_default='10.00',
                    existing_type=sa.DECIMAL(5, 2), existing_nullable=False)
