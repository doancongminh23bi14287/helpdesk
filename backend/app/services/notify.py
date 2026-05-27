# backend/app/services/notify.py
from sqlalchemy.orm import Session
from app.models.notification import Notification


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    type: str = "info",
    ref_ticket_id: int | None = None,
) -> Notification:
    """Create and flush (but do not commit) a notification record."""
    notif = Notification(
        user_id=user_id,
        title=title,
        content=content,
        type=type,
        ref_ticket_id=ref_ticket_id,
    )
    db.add(notif)
    db.flush()
    return notif
