# backend/app/api/notifications.py
from math import ceil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.core.deps import get_current_user
from app.core.scoping import scope_notifications
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return current user's notifications paginated, unread first."""
    q = db.query(Notification)
    q = scope_notifications(q, user, db)
    q = q.order_by(Notification.is_read.asc(), Notification.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return count of unread notifications for current user."""
    count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,  # noqa: E712
    ).count()
    return {"unread": count}


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
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif
