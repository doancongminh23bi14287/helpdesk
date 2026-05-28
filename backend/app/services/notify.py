# backend/app/services/notify.py
import asyncio
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
    # Fire-and-forget Socket.IO emit
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_emit_notification(user_id, {
                "id": notif.id,
                "title": title,
                "type": type,
                "ref_ticket_id": ref_ticket_id,
            }))
    except Exception:
        pass  # Socket.IO emit failure must never break the DB write
    return notif


async def _emit_notification(user_id: int, data: dict):
    from app.socketio_server import notify_user
    try:
        await notify_user(user_id, "notification", data)
    except Exception:
        pass
