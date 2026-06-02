from sqlalchemy import BigInteger, Column, String, Text, DateTime, Enum, Boolean, DECIMAL, ForeignKey, UniqueConstraint
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


class PriceList(Base):
    __tablename__ = "price_lists"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    currency = Column(String(10), nullable=False, default="VND", server_default="VND")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class PriceListItem(Base):
    __tablename__ = "price_list_items"
    __table_args__ = (UniqueConstraint("price_list_id", "item_id", name="uq_pli"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    price_list_id = Column(BigInteger, ForeignKey("price_lists.id"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    unit_price = Column(DECIMAL(15, 2), nullable=False)
