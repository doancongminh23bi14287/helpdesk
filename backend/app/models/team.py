from sqlalchemy import BigInteger, Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id = Column(BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class StaffOrgAssignment(Base):
    __tablename__ = "staff_org_assignments"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    org_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
