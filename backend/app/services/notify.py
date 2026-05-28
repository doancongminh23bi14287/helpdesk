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
    # Fire-and-forget Socket.IO emit (only when called from async context)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_emit_notification(user_id, {
            "id": notif.id,
            "title": title,
            "type": type,
            "ref_ticket_id": ref_ticket_id,
        }))
    except RuntimeError:
        pass  # No running loop (sync route context) — emit skipped, DB write still succeeds
    return notif


async def _emit_notification(user_id: int, data: dict):
    from app.socketio_server import notify_user
    try:
        await notify_user(user_id, "notification", data)
    except Exception:
        pass
