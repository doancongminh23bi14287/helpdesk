# backend/app/services/notify.py
import asyncio
import json
import logging
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

NOTIFICATION_CHANNEL = "notifications:realtime"


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

    payload = {
        "id": notif.id,
        "title": title,
        "content": content,
        "type": type,
        "ref_ticket_id": ref_ticket_id,
    }

    # Async path (FastAPI request context): schedule Socket.IO emit directly.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_emit_notification(user_id, payload))
        return notif
    except RuntimeError:
        pass  # No running event loop — Celery sync context, fall through.

    # Celery sync path: publish to Redis pub/sub so the FastAPI process
    # picks it up via redis_notification_subscriber and emits via Socket.IO.
    try:
        redis_client.publish(
            NOTIFICATION_CHANNEL,
            json.dumps({"user_id": user_id, "notification": payload}),
        )
    except Exception as exc:
        # Redis publish failure is non-fatal — DB record is already written.
        logger.warning("Redis publish failed for notification %s: %s", notif.id, exc)

    return notif


async def _emit_notification(user_id: int, data: dict):
    from app.socketio_server import notify_user
    try:
        await notify_user(user_id, "new_notification", data)
    except Exception:
        pass
