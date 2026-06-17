"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _has(table: str) -> bool:
    return inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("contact_email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column(
                "status",
                sa.Enum("active", "inactive", "suspended"),
                nullable=False,
                server_default="active",
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_org_code"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_org_status", "organizations", ["status"])

    if not _has("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("org_id", sa.BigInteger(), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(200), nullable=False),
            sa.Column(
                "role",
                sa.Enum("admin", "staff", "customer"),
                nullable=False,
                server_default="customer",
            ),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("is_active", sa.SmallInteger(), nullable=False, server_default="1"),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_user_email"),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_user_org"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_user_role", "users", ["role"])
        op.create_index("idx_user_org", "users", ["org_id"])

    if not _has("teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    if not _has("team_members"):
        op.create_table(
            "team_members",
            sa.Column("team_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("team_id", "user_id"),
            sa.ForeignKeyConstraint(
                ["team_id"], ["teams.id"], name="fk_tm_team", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], name="fk_tm_user", ondelete="CASCADE"
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    if not _has("staff_org_assignments"):
        op.create_table(
            "staff_org_assignments",
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("org_id", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("user_id", "org_id"),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], name="fk_soa_user", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["org_id"], ["organizations.id"], name="fk_soa_org", ondelete="CASCADE"
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    if not _has("service_categories"):
        op.create_table(
            "service_categories",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uq_svc_cat_slug"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    if not _has("services"):
        op.create_table(
            "services",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("org_id", sa.BigInteger(), nullable=False),
            sa.Column("category_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "type",
                sa.Enum("saas", "hosting", "other"),
                nullable=False,
                server_default="saas",
            ),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("domain", sa.String(255), nullable=True),
            sa.Column(
                "status",
                sa.Enum("active", "inactive", "cancelled", "past_due"),
                nullable=False,
                server_default="active",
            ),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column("disk_usage", sa.String(50), nullable=True),
            sa.Column("monthly_cost", sa.DECIMAL(15, 2), nullable=True, server_default="0"),
            sa.Column(
                "billing_cycle",
                sa.Enum("monthly", "quarterly", "yearly"),
                nullable=True,
                server_default="monthly",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_service_org"),
            sa.ForeignKeyConstraint(
                ["category_id"], ["service_categories.id"], name="fk_service_cat"
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_service_org", "services", ["org_id"])
        op.create_index("idx_service_status", "services", ["status"])
        op.create_index("idx_service_expiry", "services", ["expiry_date"])

    if not _has("sla_policies"):
        op.create_table(
            "sla_policies",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column(
                "priority",
                sa.Enum("Low", "Medium", "High", "Urgent"),
                nullable=False,
            ),
            sa.Column("response_hours", sa.DECIMAL(5, 2), nullable=False),
            sa.Column("resolution_hours", sa.DECIMAL(5, 2), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("priority", name="uq_sla_priority"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    if not _has("tickets"):
        op.create_table(
            "tickets",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("org_id", sa.BigInteger(), nullable=False),
            sa.Column("service_id", sa.BigInteger(), nullable=True),
            sa.Column("subject", sa.String(300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.Enum("Open", "In Progress", "Waiting", "Resolved", "Closed"),
                nullable=False,
                server_default="Open",
            ),
            sa.Column(
                "priority",
                sa.Enum("Low", "Medium", "High", "Urgent"),
                nullable=False,
                server_default="Medium",
            ),
            sa.Column(
                "ticket_type",
                sa.Enum(
                    "Bug", "Incident", "Question", "Unspecified",
                    "Service SaaS", "Service Hosting", "Renewal",
                ),
                nullable=False,
                server_default="Unspecified",
            ),
            sa.Column(
                "source",
                sa.Enum("portal", "email", "phone", "manual"),
                nullable=False,
                server_default="portal",
            ),
            sa.Column("raised_by", sa.BigInteger(), nullable=True),
            sa.Column("raised_by_email", sa.String(255), nullable=True),
            sa.Column("assignee_id", sa.BigInteger(), nullable=True),
            sa.Column("team_id", sa.BigInteger(), nullable=True),
            sa.Column("response_by", sa.DateTime(), nullable=True),
            sa.Column("resolution_by", sa.DateTime(), nullable=True),
            sa.Column("first_responded_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "sla_state",
                sa.Enum("green", "amber", "red", "breached"),
                nullable=True,
                server_default="green",
            ),
            sa.Column("is_deleted", sa.SmallInteger(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_ticket_org"),
            sa.ForeignKeyConstraint(
                ["service_id"], ["services.id"], name="fk_ticket_service"
            ),
            sa.ForeignKeyConstraint(
                ["raised_by"], ["users.id"], name="fk_ticket_raiser"
            ),
            sa.ForeignKeyConstraint(
                ["assignee_id"], ["users.id"], name="fk_ticket_assignee"
            ),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_ticket_team"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_ticket_org", "tickets", ["org_id"])
        op.create_index("idx_ticket_status", "tickets", ["status"])
        op.create_index("idx_ticket_priority", "tickets", ["priority"])
        op.create_index("idx_ticket_assignee", "tickets", ["assignee_id"])
        op.create_index("idx_ticket_created", "tickets", ["created_at"])
        op.execute("ALTER TABLE tickets ADD FULLTEXT INDEX ft_ticket_subject (subject)")

    if not _has("ticket_replies"):
        op.create_table(
            "ticket_replies",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("ticket_id", sa.BigInteger(), nullable=False),
            sa.Column("author_id", sa.BigInteger(), nullable=True),
            sa.Column("author_email", sa.String(255), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_internal", sa.SmallInteger(), nullable=False, server_default="0"),
            sa.Column(
                "source",
                sa.Enum("portal", "email", "manual"),
                nullable=False,
                server_default="portal",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["ticket_id"], ["tickets.id"], name="fk_reply_ticket", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_reply_author"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_reply_ticket", "ticket_replies", ["ticket_id"])

    if not _has("ticket_activities"):
        op.create_table(
            "ticket_activities",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("ticket_id", sa.BigInteger(), nullable=False),
            sa.Column("actor_id", sa.BigInteger(), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("from_value", sa.String(100), nullable=True),
            sa.Column("to_value", sa.String(100), nullable=True),
            sa.Column("detail", sa.String(255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["ticket_id"], ["tickets.id"], name="fk_act_ticket", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_act_actor"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_act_ticket", "ticket_activities", ["ticket_id"])

    if not _has("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column(
                "type",
                sa.Enum("info", "sla", "assignment", "reply", "expiry"),
                nullable=False,
                server_default="info",
            ),
            sa.Column("ref_ticket_id", sa.BigInteger(), nullable=True),
            sa.Column("is_read", sa.SmallInteger(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], name="fk_notif_user", ondelete="CASCADE"
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_notif_user", "notifications", ["user_id", "is_read"])

    if not _has("email_log"):
        op.create_table(
            "email_log",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("message_id", sa.String(255), nullable=True),
            sa.Column("from_email", sa.String(255), nullable=True),
            sa.Column("subject", sa.String(300), nullable=True),
            sa.Column("ticket_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "action",
                sa.Enum("created", "appended", "skipped", "error"),
                nullable=False,
            ),
            sa.Column("detail", sa.String(255), nullable=True),
            sa.Column(
                "processed_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("message_id", name="uq_email_log_msgid"),
            sa.ForeignKeyConstraint(
                ["ticket_id"], ["tickets.id"], name="fk_email_ticket"
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_email_from", "email_log", ["from_email"])

    if not _has("ticket_attachments"):
        op.create_table(
            "ticket_attachments",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("ticket_id", sa.BigInteger(), nullable=True),
            sa.Column("reply_id", sa.BigInteger(), nullable=True),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("file_size", sa.BigInteger(), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["ticket_id"], ["tickets.id"], name="fk_ta_ticket", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["reply_id"],
                ["ticket_replies.id"],
                name="fk_ta_reply",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name="fk_ta_user"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )

    # Seed default data (idempotent)
    op.execute(
        "INSERT INTO sla_policies (priority, response_hours, resolution_hours) VALUES"
        " ('Urgent', 0.25, 2), ('High', 1, 8), ('Medium', 4, 24), ('Low', 8, 72)"
        " ON DUPLICATE KEY UPDATE response_hours=VALUES(response_hours)"
    )
    op.execute(
        "INSERT INTO service_categories (name, slug) VALUES"
        " ('SaaS Subscription', 'saas'), ('Web Hosting', 'hosting'),"
        " ('Domain', 'domain'), ('Support Package', 'support')"
        " ON DUPLICATE KEY UPDATE name=VALUES(name)"
    )
    op.execute(
        "INSERT INTO organizations (name, code, contact_email, status) VALUES"
        " ('OSD Provider', 'PROVIDER', 'admin@osd.vn', 'active')"
        " ON DUPLICATE KEY UPDATE name=VALUES(name)"
    )


def downgrade() -> None:
    # Drop in reverse FK dependency order
    if _has("ticket_attachments"):
        op.drop_table("ticket_attachments")
    if _has("email_log"):
        op.drop_table("email_log")
    if _has("notifications"):
        op.drop_table("notifications")
    if _has("ticket_activities"):
        op.drop_table("ticket_activities")
    if _has("ticket_replies"):
        op.drop_table("ticket_replies")
    if _has("tickets"):
        op.drop_table("tickets")
    if _has("sla_policies"):
        op.drop_table("sla_policies")
    if _has("services"):
        op.drop_table("services")
    if _has("service_categories"):
        op.drop_table("service_categories")
    if _has("staff_org_assignments"):
        op.drop_table("staff_org_assignments")
    if _has("team_members"):
        op.drop_table("team_members")
    if _has("teams"):
        op.drop_table("teams")
    if _has("users"):
        op.drop_table("users")
    if _has("organizations"):
        op.drop_table("organizations")
