from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class TicketTransferRequest(Base):
    __tablename__ = "ticket_transfer_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    from_staff_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    to_staff_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(Enum("pending", "accepted", "declined"), nullable=False, default="pending", server_default="pending")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)

    from_staff = relationship("User", foreign_keys=[from_staff_id])
    to_staff = relationship("User", foreign_keys=[to_staff_id])
