from sqlalchemy import BigInteger, Column, Integer, String, Text, Enum, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    service_id = Column(BigInteger, ForeignKey("services.id"))
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=True)
    task_id = Column(BigInteger, ForeignKey("project_tasks.id", ondelete="SET NULL"), nullable=True)
    subject = Column(String(300), nullable=False)
    description = Column(Text)
    status = Column(
        Enum("Open", "In Progress", "Waiting", "Resolved", "Closed"),
        nullable=False, default="Open",
    )
    priority = Column(Enum("Low", "Medium", "High", "Urgent"), nullable=False, default="Medium")
    ticket_type = Column(
        Enum(
            "Question", "Bug", "Incident", "Task Request", "Change Request",
            "Feature Request", "Content Request", "SEO Request",
            "Approval Required", "Complaint", "Renewal", "Other",
        ),
        nullable=False, default="Question",
    )
    source = Column(Enum("portal", "email", "phone", "manual"), nullable=False, default="portal")
    raised_by = Column(BigInteger, ForeignKey("users.id"))
    raised_by_email = Column(String(255))
    assignee_id = Column(BigInteger, ForeignKey("users.id"))  # primary assignee — never drop
    assignment_mode = Column(
        Enum("none", "auto", "manual"),
        nullable=False,
        default="auto",
        server_default="auto",
    )
    team_id = Column(BigInteger, ForeignKey("teams.id"))
    response_by = Column(DateTime)
    resolution_by = Column(DateTime)
    first_responded_at = Column(DateTime)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    sla_paused_at = Column(DateTime, nullable=True)
    sla_paused_total_seconds = Column(Integer, nullable=False, default=0, server_default='0')
    sla_state = Column(Enum("green", "amber", "red", "breached"), default="green")
    is_deleted = Column(Boolean, nullable=False, default=False)
    # Personal archive flag for the ticket creator — hides the ticket from the
    # customer's default list only; staff/admin views ignore it entirely
    customer_archived = Column(Boolean, nullable=False, default=False, server_default='0')
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    ticket_assignees = relationship(
        "TicketAssignee",
        foreign_keys="TicketAssignee.ticket_id",
        cascade="all, delete-orphan",
    )


class TicketAssignee(Base):
    __tablename__ = "ticket_assignees"
    __table_args__ = (
        UniqueConstraint("ticket_id", "user_id", name="uq_ticket_assignees_ticket_user"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    assigned_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TicketReply(Base):
    __tablename__ = "ticket_replies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(BigInteger, ForeignKey("users.id"))
    author_email = Column(String(255))
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False)
    source = Column(Enum("portal", "email", "manual"), nullable=False, default="portal")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TicketActivity(Base):
    __tablename__ = "ticket_activities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(BigInteger, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    from_value = Column(String(100))
    to_value = Column(String(100))
    detail = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
