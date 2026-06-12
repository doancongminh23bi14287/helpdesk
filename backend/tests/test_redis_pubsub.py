# backend/tests/test_redis_pubsub.py
"""
Unit tests for the Redis pub/sub notification bridge.

Verifies:
  - Celery sync context (no event loop) → redis_client.publish called
  - FastAPI async context (event loop present) → socket emit used, publish NOT called
  - redis_notification_subscriber → sio.emit called with correct room and data
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_db(notif_id=1):
    """Return a mock SQLAlchemy session that sets notif.id on flush."""
    db = MagicMock()

    def _flush():
        # Simulate the DB assigning an id when the row is flushed.
        for obj in db.add.call_args_list:
            obj_arg = obj[0][0]
            obj_arg.id = notif_id

    db.flush.side_effect = _flush
    return db


# ── test 1: Celery path publishes to Redis ────────────────────────────────────

def test_celery_context_publishes_to_redis():
    """When there is no running event loop, publish to Redis instead of emit."""
    from app.services.notify import create_notification, NOTIFICATION_CHANNEL

    db = _make_db(notif_id=7)

    with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")), \
         patch("app.services.notify.redis_client") as mock_redis:

        create_notification(db, user_id=42, title="SLA breach", content="Ticket overdue", type="warning")

    mock_redis.publish.assert_called_once()
    channel_arg, payload_arg = mock_redis.publish.call_args[0]

    assert channel_arg == NOTIFICATION_CHANNEL
    data = json.loads(payload_arg)
    assert data["user_id"] == 42
    assert data["notification"]["id"] == 7
    assert data["notification"]["title"] == "SLA breach"
    assert data["notification"]["content"] == "Ticket overdue"
    assert data["notification"]["type"] == "warning"


# ── test 2: FastAPI async path uses socket emit, not Redis ────────────────────

def test_fastapi_context_uses_socket_emit_not_redis():
    """When a running event loop is present, schedule emit and skip Redis publish."""
    from app.services.notify import create_notification

    db = _make_db(notif_id=3)

    mock_loop = MagicMock()
    # Close the coroutine immediately so Python doesn't warn about it never being awaited.
    mock_loop.create_task = MagicMock(side_effect=lambda coro: coro.close())

    with patch("asyncio.get_running_loop", return_value=mock_loop), \
         patch("app.services.notify.redis_client") as mock_redis:

        create_notification(db, user_id=5, title="Reply", content="You have a reply", type="info")

    # loop.create_task must have been called (async emit path)
    mock_loop.create_task.assert_called_once()

    # Redis publish must NOT have been called
    mock_redis.publish.assert_not_called()


# ── test 3: Subscriber emits to the correct Socket.IO room ───────────────────

def test_subscriber_emits_on_redis_message():
    """Subscriber reads from pub/sub and emits to the right user room."""
    from app.socketio_server import redis_notification_subscriber

    notification_payload = {
        "id": 99,
        "title": "Invoice ready",
        "content": "Your invoice is ready",
        "type": "info",
        "ref_ticket_id": None,
    }
    message_data = json.dumps({"user_id": 11, "notification": notification_payload})

    async def fake_listen():
        yield {"type": "subscribe", "data": 1}       # ignored by subscriber
        yield {"type": "message", "data": message_data}
        # Generator exhausts — subscriber loop exits cleanly.

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = fake_listen

    mock_aioredis_instance = MagicMock()
    mock_aioredis_instance.pubsub = MagicMock(return_value=mock_pubsub)

    mock_sio = MagicMock()
    mock_sio.emit = AsyncMock()

    async def run():
        with patch("app.socketio_server.aioredis.Redis", return_value=mock_aioredis_instance):
            await redis_notification_subscriber(mock_sio)

    asyncio.run(run())

    mock_sio.emit.assert_called_once_with(
        "new_notification",
        notification_payload,
        room="user_11",
    )
