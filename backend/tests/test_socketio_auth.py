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
    save_session.assert_awaited_once_with(
        "socket-1", {"user_id": customer_user.id, "role": "customer"}
    )


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


def test_socket_connect_marks_authenticated_staff_present(staff_token, staff_user):
    from app.socketio_server import connect, sio

    with patch.object(sio, "enter_room", new=AsyncMock()), patch.object(
        sio, "save_session", new=AsyncMock()
    ), patch(
        "app.socketio_server.SessionLocal",
        side_effect=TestingSessionLocal,
    ), patch("app.socketio_server.mark_user_present") as mark_present:
        asyncio.run(connect("staff-socket", {}, {"token": staff_token}))

    mark_present.assert_called_once_with(staff_user.id)


def test_unauthenticated_presence_heartbeat_is_rejected():
    from app.socketio_server import presence_heartbeat, sio

    with patch.object(sio, "get_session", new=AsyncMock(return_value=None)):
        result = asyncio.run(presence_heartbeat("unknown-socket"))

    assert result == {"ok": False, "error": "unauthenticated"}


def test_presence_heartbeat_cannot_impersonate_another_user(staff_user):
    from app.socketio_server import presence_heartbeat, sio

    session = {"user_id": staff_user.id, "role": "staff"}
    with patch.object(sio, "get_session", new=AsyncMock(return_value=session)), patch(
        "app.socketio_server.mark_user_present", return_value=True
    ) as mark_present:
        result = asyncio.run(
            presence_heartbeat("staff-socket", {"user_id": staff_user.id + 999})
        )

    assert result == {"ok": True, "eligible": True}
    mark_present.assert_called_once_with(staff_user.id)


def test_customer_heartbeat_does_not_create_assignment_presence(customer_user):
    from app.socketio_server import presence_heartbeat, sio

    session = {"user_id": customer_user.id, "role": "customer"}
    with patch.object(sio, "get_session", new=AsyncMock(return_value=session)), patch(
        "app.socketio_server.mark_user_present"
    ) as mark_present:
        result = asyncio.run(presence_heartbeat("customer-socket"))

    assert result == {"ok": True, "eligible": False}
    mark_present.assert_not_called()
