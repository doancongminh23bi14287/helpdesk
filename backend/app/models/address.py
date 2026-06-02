from sqlalchemy import BigInteger, Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    label = Column(String(100), nullable=False)
    street = Column(String(255))
    city = Column(String(100))
    province = Column(String(100))
    country = Column(String(100), nullable=False, default="Vietnam", server_default="Vietnam")
    postal_code = Column(String(20))
    is_default = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
