# backend/app/api/notifications.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.core.deps import get_current_user
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return current user's notifications, unread first then by created_at desc."""
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.is_read.asc(), Notification.created_at.desc())
        .all()
    )


@router.put("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}


@router.put("/{notif_id}/read", response_model=NotificationOut)
def mark_read(
    notif_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == user.id,
    ).first()
    if not notif:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif
