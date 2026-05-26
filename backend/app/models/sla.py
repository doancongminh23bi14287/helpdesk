from sqlalchemy import BigInteger, Column, Enum, DECIMAL, DateTime
from sqlalchemy.sql import func
from app.database import Base


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    priority = Column(Enum("Low", "Medium", "High", "Urgent"), nullable=False, unique=True)
    response_hours = Column(DECIMAL(5, 2), nullable=False)
    resolution_hours = Column(DECIMAL(5, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
