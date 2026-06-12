from sqlalchemy import BigInteger, Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True)
    reply_id = Column(BigInteger, ForeignKey("ticket_replies.id", ondelete="CASCADE"), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    detected_mime = Column(String(255), nullable=True)
    sha256 = Column(String(64), nullable=True)
    uploaded_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
