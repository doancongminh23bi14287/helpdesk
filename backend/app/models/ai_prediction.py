from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class TicketAiPrediction(Base):
    __tablename__ = "ticket_ai_predictions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    predicted_category = Column(String(100), nullable=False)
    predicted_priority = Column(String(50), nullable=False)
    predicted_department = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    ticket = relationship("Ticket", backref="ai_predictions")


class AiReplySuggestion(Base):
    __tablename__ = "ai_reply_suggestions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    reply_id = Column(BigInteger, ForeignKey("ticket_replies.id", ondelete="SET NULL"), nullable=True)
    prompt_snapshot_hash = Column(String(64), nullable=False)
    generated_text = Column(Text, nullable=False)
    accepted = Column(Boolean, nullable=False, default=False)
    edited = Column(Boolean, nullable=False, default=False)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    ticket = relationship("Ticket", backref="ai_reply_suggestions")
    creator = relationship("User", foreign_keys=[created_by])
