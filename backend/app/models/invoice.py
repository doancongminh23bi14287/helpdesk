from sqlalchemy import BigInteger, Column, String, Text, Integer, Date, DateTime, Enum, DECIMAL, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from app.database import Base


class InvoiceNumberSeq(Base):
    __tablename__ = "invoice_number_seq"
    year = Column(Integer, primary_key=True)
    last_seq = Column(Integer, nullable=False, default=0, server_default="0")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invoice_number = Column(String(50), nullable=False, unique=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    status = Column(
        Enum("draft", "sent", "paid", "overdue", "cancelled", name="invoice_status"),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    subtotal = Column(DECIMAL(15, 2), nullable=False)
    tax_rate = Column(DECIMAL(5, 2), nullable=False, default="10.00", server_default="10.00")
    tax_amount = Column(DECIMAL(15, 2), nullable=False)
    total = Column(DECIMAL(15, 2), nullable=False)
    notes = Column(Text, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id = Column(BigInteger, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=True)
    description = Column(String(300), nullable=False)
    quantity = Column(DECIMAL(10, 2), nullable=False, default="1.00", server_default="1.00")
    unit_price = Column(DECIMAL(15, 2), nullable=False)
    line_total = Column(DECIMAL(15, 2), nullable=False)


def generate_invoice_number(db: Session, year: int) -> str:
    """
    Generate a unique invoice number INV-{year}-{seq:04d}.
    Uses SELECT FOR UPDATE to prevent race conditions.
    Creates the sequence row if it doesn't exist.
    """
    from sqlalchemy import text

    # Lock the row for this year (or create it)
    seq_row = db.query(InvoiceNumberSeq).filter_by(year=year).with_for_update().first()
    if seq_row is None:
        seq_row = InvoiceNumberSeq(year=year, last_seq=0)
        db.add(seq_row)
        db.flush()

    seq_row.last_seq += 1
    db.flush()

    return f"INV-{year}-{seq_row.last_seq:04d}"
