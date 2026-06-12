from sqlalchemy import BigInteger, Column, String, Text, DateTime, Enum, Boolean, DECIMAL
from sqlalchemy.sql import func
from app.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    type = Column(Enum("saas", "hosting", "domain", "support", "other", name="item_type"), nullable=False)
    unit_price = Column(DECIMAL(15, 2), nullable=False)
    unit = Column(String(50), nullable=False, default="month", server_default="month")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
