from datetime import datetime
from sqlalchemy import BigInteger, Column, Integer, String, DateTime, ForeignKey
from app.database import Base


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False)   # sha256 of 6-digit code
    expires_at = Column(DateTime, nullable=False)    # utcnow + 10 minutes
    used_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
