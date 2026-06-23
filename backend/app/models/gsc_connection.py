from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class GscConnection(Base):
    __tablename__ = "gsc_connections"
    __table_args__ = (UniqueConstraint("org_id", name="uq_gsc_connections_org_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    property_url = Column(String(500), nullable=True)
    # TODO: encrypt at rest for production (currently stored as plain text)
    refresh_token = Column(Text, nullable=False)
    access_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    connected_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    status = Column(String(50), nullable=False, server_default="connected")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
