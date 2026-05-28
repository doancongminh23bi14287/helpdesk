# backend/app/socketio_server.py
"""
Socket.IO server — realtime notifications.

Clients connect with JWT in auth: { token: "<access_token>" }
On connect, user joins room "user_{user_id}" for targeted delivery.
notify_user(user_id, event_name, data) broadcasts to that room.
"""
import socketio
from app.core.security import decode_token
from app.database import SessionLocal
from app.models.user import User

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
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

    # Verify user exists and is active
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
