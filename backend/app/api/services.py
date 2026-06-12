# backend/app/api/services.py
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.service import Service
from app.models.user import User
from app.core.deps import get_current_user
from app.core.scoping import scope_services
from app.schemas.organization import ServiceOut

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=List[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return services scoped to the user's role."""
    query = db.query(Service)
    query = scope_services(query, user, db)
    return query.order_by(Service.name.asc()).all()
