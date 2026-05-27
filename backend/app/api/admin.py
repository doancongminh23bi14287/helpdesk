# backend/app/api/admin.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.core.deps import require_admin
from app.services.email_piping import process_inbox

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/email/poll")
def manual_email_poll(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    count = process_inbox(db)
    return {"processed": count}
