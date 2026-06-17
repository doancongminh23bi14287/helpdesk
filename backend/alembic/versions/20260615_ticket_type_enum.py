"""change_ticket_type_enum_12_values

Revision ID: 20260615_ticket_type_enum
Revises: 7da8810a091c
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_ticket_type_enum"
down_revision: Union[str, None] = "7da8810a091c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ENUM = (
    "enum('Bug','Incident','Question','Unspecified',"
    "'Service SaaS','Service Hosting','Renewal')"
)
_NEW_ENUM = (
    "enum('Question','Bug','Incident','Task Request','Change Request',"
    "'Feature Request','Content Request','SEO Request','Approval Required',"
    "'Complaint','Renewal','Other')"
)
_SUPERSET_ENUM = (
    "enum('Bug','Incident','Question','Unspecified','Service SaaS','Service Hosting','Renewal',"
    "'Task Request','Change Request','Feature Request','Content Request','SEO Request',"
    "'Approval Required','Complaint','Other')"
)


def upgrade() -> None:
    conn = op.get_bind()

    # Log current distribution before any change
    result = conn.execute(
        sa.text("SELECT ticket_type, COUNT(*) as cnt FROM tickets GROUP BY ticket_type")
    )
    print("\n[Migration] ticket_type distribution BEFORE upgrade:")
    for row in result:
        print(f"  {row[0]}: {row[1]}")

    # Step 1: widen to superset (all old + new values)
    op.execute(
        "ALTER TABLE tickets MODIFY ticket_type "
        + _SUPERSET_ENUM
        + " NOT NULL DEFAULT 'Unspecified'"
    )

    # Step 2: map old values to new
    op.execute("UPDATE tickets SET ticket_type='Other' WHERE ticket_type='Unspecified'")
    op.execute(
        "UPDATE tickets SET ticket_type='Task Request' "
        "WHERE ticket_type IN ('Service SaaS','Service Hosting')"
    )

    # Step 3: shrink to final new enum
    op.execute(
        "ALTER TABLE tickets MODIFY ticket_type "
        + _NEW_ENUM
        + " NOT NULL DEFAULT 'Question'"
    )

    result2 = conn.execute(
        sa.text("SELECT ticket_type, COUNT(*) as cnt FROM tickets GROUP BY ticket_type")
    )
    print("\n[Migration] ticket_type distribution AFTER upgrade:")
    for row in result2:
        print(f"  {row[0]}: {row[1]}")


def downgrade() -> None:
    # Step 1: widen back to superset
    op.execute(
        "ALTER TABLE tickets MODIFY ticket_type "
        + _SUPERSET_ENUM
        + " NOT NULL DEFAULT 'Other'"
    )

    # Step 2: map new values back to old (lossy for values that have no old equivalent)
    op.execute("UPDATE tickets SET ticket_type='Service SaaS' WHERE ticket_type='Task Request'")
    op.execute("UPDATE tickets SET ticket_type='Unspecified' WHERE ticket_type='Other'")
    op.execute(
        "UPDATE tickets SET ticket_type='Unspecified' "
        "WHERE ticket_type IN ("
        "'Change Request','Feature Request','Content Request',"
        "'SEO Request','Approval Required','Complaint'"
        ")"
    )

    # Step 3: shrink to old 7-value enum
    op.execute(
        "ALTER TABLE tickets MODIFY ticket_type "
        + _OLD_ENUM
        + " NOT NULL DEFAULT 'Unspecified'"
    )
