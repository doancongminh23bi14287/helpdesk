from sqlalchemy import BigInteger, Column, String, Text, Enum, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text)
    type = Column(Enum("info", "sla", "assignment", "reply", "expiry"), nullable=False, default="info")
    ref_ticket_id = Column(BigInteger)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class EmailLog(Base):
    __tablename__ = "email_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True)
    from_email = Column(String(255))
    subject = Column(String(300))
    ticket_id = Column(BigInteger, ForeignKey("tickets.id"))
    action = Column(Enum("created", "appended", "skipped", "error"), nullable=False)
    detail = Column(String(255))
    processed_at = Column(DateTime, nullable=False, server_default=func.now())
