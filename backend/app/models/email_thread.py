from sqlalchemy import BigInteger, Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class EmailThread(Base):
    __tablename__ = "email_threads"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id"), nullable=False, index=True)
    message_id = Column(String(500), nullable=True, index=True)
    in_reply_to = Column(String(500), nullable=True, index=True)
    references = Column(String(2000), nullable=True)
    direction = Column(Enum("inbound", "outbound"), nullable=False, default="inbound")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
