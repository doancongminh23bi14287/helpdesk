from sqlalchemy import BigInteger, Column, String, Text, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id = Column(BigInteger, ForeignKey("invoices.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    method = Column(String(50), nullable=False)
    # method: "bank_transfer" | "cash" | "vnpay" | "manual" | "other"
    reference = Column(String(255), nullable=True)
    paid_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)
    paid_at = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    invoice = relationship("Invoice", back_populates="payments")
