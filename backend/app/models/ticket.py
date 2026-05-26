from sqlalchemy import BigInteger, Column, String, Text, Enum, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    service_id = Column(BigInteger, ForeignKey("services.id"))
    subject = Column(String(300), nullable=False)
    description = Column(Text)
    status = Column(
        Enum("Open", "In Progress", "Waiting", "Resolved", "Closed"),
        nullable=False, default="Open",
    )
    priority = Column(Enum("Low", "Medium", "High", "Urgent"), nullable=False, default="Medium")
    ticket_type = Column(
        Enum("Bug", "Incident", "Question", "Unspecified", "Service SaaS", "Service Hosting", "Renewal"),
        nullable=False, default="Unspecified",
    )
    source = Column(Enum("portal", "email", "phone", "manual"), nullable=False, default="portal")
    raised_by = Column(BigInteger, ForeignKey("users.id"))
    raised_by_email = Column(String(255))
    assignee_id = Column(BigInteger, ForeignKey("users.id"))
    team_id = Column(BigInteger, ForeignKey("teams.id"))
    response_by = Column(DateTime)
    resolution_by = Column(DateTime)
    first_responded_at = Column(DateTime)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    sla_state = Column(Enum("green", "amber", "red", "breached"), default="green")
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


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
