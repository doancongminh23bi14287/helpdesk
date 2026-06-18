from sqlalchemy import BigInteger, Column, String, Enum, Date, DateTime, DECIMAL, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)


class Service(Base):
    __tablename__ = "services"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    category_id = Column(BigInteger, ForeignKey("service_categories.id"))
    type = Column(Enum("saas", "hosting", "domain", "support", "other"), nullable=False, default="saas")
    name = Column(String(200), nullable=False)
    domain = Column(String(255))
    status = Column(Enum("active", "inactive", "cancelled", "past_due"), nullable=False, default="active")
    start_date = Column(Date)
    expiry_date = Column(Date)
    disk_usage = Column(String(50))
    monthly_cost = Column(DECIMAL(15, 2), default=0)
    billing_cycle = Column(Enum("monthly", "quarterly", "yearly"), default="monthly")
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
