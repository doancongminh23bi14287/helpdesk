"""add unique constraint on services.subscription_id

Revision ID: a1b2c3d4e5f6
Revises: ff73e7de64fc
Create Date: 2026-06-18 00:00:00.000000

"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'ff73e7de64fc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        'uq_services_subscription_id',
        'services',
        ['subscription_id'],
    )


def downgrade():
    op.drop_constraint('uq_services_subscription_id', 'services', type_='unique')
