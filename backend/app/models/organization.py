from sqlalchemy import BigInteger, Column, String, Text, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    contact_email = Column(String(255))
    phone = Column(String(50))
    status = Column(Enum("active", "inactive", "suspended"), nullable=False, default="active")
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
