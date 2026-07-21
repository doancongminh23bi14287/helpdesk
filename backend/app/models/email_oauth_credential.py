from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.sql import func

from app.database import Base


class EmailOAuthCredential(Base):
    """Singleton Gmail OAuth credential used by the outbound worker."""

    __tablename__ = "email_oauth_credentials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    refresh_token = Column(Text, nullable=False)
    access_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    connected_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    status = Column(String(50), nullable=False, server_default="connected")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
