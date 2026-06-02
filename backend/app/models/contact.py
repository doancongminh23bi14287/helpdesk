from sqlalchemy import BigInteger, Column, String, DateTime, Enum, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    role = Column(Enum("primary", "billing", "technical", "other", name="contact_role"), nullable=False, default="primary", server_default="primary")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
