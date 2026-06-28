from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Ga4Connection(Base):
    __tablename__ = "ga4_connections"
    __table_args__ = (UniqueConstraint("org_id", name="uq_ga4_connections_org_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    property_id = Column(String(50), nullable=True)
    property_name = Column(String(255), nullable=True)
    refresh_token = Column(Text, nullable=False)
    access_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    connected_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    status = Column(String(50), nullable=False, server_default="connected")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
