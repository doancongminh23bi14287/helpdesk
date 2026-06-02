from sqlalchemy import BigInteger, Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class LoginHistory(Base):
    __tablename__ = "login_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    status = Column(
        Enum("success", "failed", "blocked", name="login_status"),
        nullable=False,
        default="success",
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
