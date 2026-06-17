# backend/app/socketio_server.py
"""
Socket.IO server — realtime notifications.

Clients connect with JWT in auth: { token: "<access_token>" }
On connect, user joins room "user_{user_id}" for targeted delivery.
notify_user(user_id, event_name, data) broadcasts to that room.

redis_notification_subscriber() runs as a background asyncio task and
forwards messages published by Celery tasks to the correct user rooms.
"""
import json
import logging
import socketio
import redis.asyncio as aioredis
from app.core.security import decode_token
from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.services.notify import NOTIFICATION_CHANNEL

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.CORS_ORIGINS,
)


@sio.event
async def connect(sid, environ, auth):
    """Authenticate JWT on connect; join personal room."""
    token = (auth or {}).get("token")
    if not token:
        raise ConnectionRefusedError("Missing token")
    try:
        claims = decode_token(token)
        if claims.get("type") != "access":
            raise ConnectionRefusedError("Invalid token type")
        user_id = int(claims["sub"])
    except Exception:
        raise ConnectionRefusedError("Invalid token")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise ConnectionRefusedError("User not found or inactive")
    finally:
        db.close()

    await sio.enter_room(sid, f"user_{user_id}")
    await sio.save_session(sid, {"user_id": user_id})


@sio.event
async def disconnect(sid):
    session = await sio.get_session(sid)
    user_id = session.get("user_id") if session else None
    if user_id:
        await sio.leave_room(sid, f"user_{user_id}")


async def notify_user(user_id: int, event: str, data: dict):
    """Emit event to a specific user's room. Call from anywhere in the app."""
    await sio.emit(event, data, room=f"user_{user_id}")


async def redis_notification_subscriber(sio_server):
    """
    Subscribe to the Redis pub/sub notification channel and forward
    each message to the correct Socket.IO user room.

    Runs as a long-lived background asyncio task started at app startup.
    Celery tasks publish here (sync context); this picks them up and emits
    via Socket.IO in the async FastAPI process.
    """
    r = aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
    )
    pubsub = r.pubsub()
    await pubsub.subscribe(NOTIFICATION_CHANNEL)

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            user_id = data["user_id"]
            notification = data["notification"]
            await sio_server.emit(
                "new_notification",
                notification,
                room=f"user_{user_id}",
            )
        except Exception as exc:
            logger.warning("Subscriber error: %s", exc)
