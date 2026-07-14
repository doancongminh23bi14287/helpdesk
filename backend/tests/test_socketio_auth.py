import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import decode_token
from app.models.user_session import UserSession
from tests.conftest import TestingSessionLocal


def test_socket_connect_accepts_current_session(customer_token, customer_user):
    from app.socketio_server import connect, sio

    enter_room = AsyncMock()
    save_session = AsyncMock()
    with patch.object(sio, "enter_room", enter_room), patch.object(
        sio, "save_session", save_session
    ), patch(
        "app.socketio_server.SessionLocal",
        side_effect=TestingSessionLocal,
    ):
        asyncio.run(connect("socket-1", {}, {"token": customer_token}))

    enter_room.assert_awaited_once_with("socket-1", f"user_{customer_user.id}")
    save_session.assert_awaited_once_with("socket-1", {"user_id": customer_user.id})


def test_socket_connect_rejects_revoked_session(
    customer_token, customer_user, db
):
    from app.socketio_server import connect

    claims = decode_token(customer_token)
    session = db.query(UserSession).filter(
        UserSession.user_id == customer_user.id,
        UserSession.current_jti == claims["jti"],
    ).one()
    session.is_active = False
    db.commit()

    with patch(
        "app.socketio_server.SessionLocal",
        side_effect=TestingSessionLocal,
    ), pytest.raises(ConnectionRefusedError, match="revoked"):
        asyncio.run(connect("socket-2", {}, {"token": customer_token}))
