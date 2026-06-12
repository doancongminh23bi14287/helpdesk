import sqlalchemy as sa
from sqlalchemy import BigInteger, Column, Integer, String, DateTime, Enum, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(Enum("admin", "staff", "customer"), nullable=False, default="customer")
    phone = Column(String(50))
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False, server_default=sa.text("0"))
    last_login_at = Column(DateTime)
    last_assigned_at = Column(DateTime, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    avatar_path = Column(String(500), nullable=True)
    avatar_mime_type = Column(String(100), nullable=True)
    avatar_size_bytes = Column(Integer, nullable=True)
    avatar_updated_at = Column(DateTime, nullable=True)
    avatar_color = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
