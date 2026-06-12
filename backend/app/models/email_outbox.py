from sqlalchemy import BigInteger, Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email_type = Column(String(50), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    recipient_name = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_retries = Column(Integer, nullable=False, default=3, server_default="3")
    last_error = Column(Text, nullable=True)
    related_type = Column(String(50), nullable=True)
    related_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    scheduled_at = Column(DateTime, nullable=False, server_default=func.now())
    sent_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
