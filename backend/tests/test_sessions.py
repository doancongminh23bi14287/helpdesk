# backend/tests/test_sessions.py
"""
Integration tests for per-session JWT tracking and refresh token rotation.

Verifies:
  - Login creates a UserSession record in the DB
  - Refresh rotates tokens (old session revoked, new session created)
  - Refresh-token reuse revokes all sessions (theft detection)
  - Logout revokes the specific session
  - Expired sessions cannot be refreshed
  - Password change revokes all sessions
"""
import pytest
from datetime import datetime, timedelta, timezone


# ── helpers ───────────────────────────────────────────────────────────────────

def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()  # {access_token, refresh_token}


def _refresh(client, refresh_token):
    return client.post("/api/auth/refresh", json={"refresh_token": refresh_token})


def _logout(client, access_token, refresh_token):
    return client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )


# ── tests ─────────────────────────────────────────────────────────────────────

def test_login_creates_session_record(client, db, customer_user):
    from app.models.user_session import UserSession
    from app.core.security import hash_token

    tokens = _login(client, "customer@test.com", "cust123")
    token_hash = hash_token(tokens["refresh_token"])

    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == token_hash,
    ).first()

    assert session is not None
    assert session.user_id == customer_user.id
    assert session.is_active is True
    assert session.current_jti is not None


def test_refresh_rotates_token(client, db, customer_user):
    from app.models.user_session import UserSession
    from app.core.security import hash_token

    tokens = _login(client, "customer@test.com", "cust123")
    old_hash = hash_token(tokens["refresh_token"])

    r = _refresh(client, tokens["refresh_token"])
    assert r.status_code == 200, r.text
    new_data = r.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data

    # Old session must be revoked
    old_session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == old_hash,
    ).first()
    db.refresh(old_session)
    assert old_session.is_active is False
    assert old_session.revoked_at is not None

    # New session must exist and be active
    new_hash = hash_token(new_data["refresh_token"])
    new_session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == new_hash,
    ).first()
    assert new_session is not None
    assert new_session.is_active is True


def test_refresh_reuse_revokes_all_sessions(client, db, customer_user):
    from app.models.user_session import UserSession

    tokens = _login(client, "customer@test.com", "cust123")

    # Consume the refresh token once (legitimate rotation)
    r1 = _refresh(client, tokens["refresh_token"])
    assert r1.status_code == 200

    # Reuse the already-rotated token — theft detected
    r2 = _refresh(client, tokens["refresh_token"])
    assert r2.status_code == 401

    # All sessions for this user must be revoked
    active_sessions = db.query(UserSession).filter(
        UserSession.user_id == customer_user.id,
        UserSession.is_active.is_(True),
    ).count()
    assert active_sessions == 0


def test_logout_revokes_session(client, db, customer_user):
    from app.models.user_session import UserSession
    from app.core.security import hash_token

    tokens = _login(client, "customer@test.com", "cust123")
    token_hash = hash_token(tokens["refresh_token"])

    r = _logout(client, tokens["access_token"], tokens["refresh_token"])
    assert r.status_code == 200

    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == token_hash,
    ).first()
    db.refresh(session)
    assert session.is_active is False


def test_list_sessions_marks_current_session(client, customer_user):
    tokens = _login(client, "customer@test.com", "cust123")

    r = client.get(
        "/api/auth/sessions",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert r.status_code == 200, r.text
    sessions = r.json()
    assert len(sessions) == 1
    assert sessions[0]["is_active"] is True
    assert sessions[0]["is_current"] is True
    assert "refresh_token" not in sessions[0]


def test_revoke_session_endpoint_revokes_only_own_session(client, db, customer_user):
    from app.models.user_session import UserSession

    tokens = _login(client, "customer@test.com", "cust123")
    session = db.query(UserSession).filter(UserSession.user_id == customer_user.id).first()

    r = client.delete(
        f"/api/auth/sessions/{session.id}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert r.status_code == 200, r.text
    db.refresh(session)
    assert session.is_active is False


def test_logout_all_revokes_all_sessions(client, db, customer_user):
    from app.models.user_session import UserSession

    tokens = _login(client, "customer@test.com", "cust123")
    _login(client, "customer@test.com", "cust123")

    r = client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert r.status_code == 200, r.text
    active_count = db.query(UserSession).filter(
        UserSession.user_id == customer_user.id,
        UserSession.is_active.is_(True),
    ).count()
    assert active_count == 0


def test_login_clears_stale_user_blacklist(client, customer_user):
    from app.core.redis_client import redis_client
    from app.core.security import blacklist_user_tokens, is_user_blacklisted

    blacklist_user_tokens(customer_user.id, redis_client)
    assert is_user_blacklisted(customer_user.id, redis_client) is True

    tokens = _login(client, "customer@test.com", "cust123")
    assert is_user_blacklisted(customer_user.id, redis_client) is False

    r = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200, r.text


def test_expired_session_cannot_refresh(client, db, customer_user):
    from app.models.user_session import UserSession
    from app.core.security import hash_token

    tokens = _login(client, "customer@test.com", "cust123")
    token_hash = hash_token(tokens["refresh_token"])

    # Force-expire the session in the DB
    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == token_hash,
    ).first()
    session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db.commit()

    r = _refresh(client, tokens["refresh_token"])
    assert r.status_code == 401


def test_password_change_revokes_all_sessions(client, db, customer_user):
    from app.models.user_session import UserSession

    # Create two sessions by logging in twice
    tokens1 = _login(client, "customer@test.com", "cust123")
    tokens2 = _login(client, "customer@test.com", "cust123")

    active_before = db.query(UserSession).filter(
        UserSession.user_id == customer_user.id,
        UserSession.is_active.is_(True),
    ).count()
    assert active_before == 2

    # Change password — uses tokens1 access token
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "cust123", "new_password": "newpass123"},
        headers={"Authorization": f"Bearer {tokens1['access_token']}"},
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    active_after = db.query(UserSession).filter(
        UserSession.user_id == customer_user.id,
        UserSession.is_active.is_(True),
    ).count()
    assert active_after == 0

    # Neither old refresh token can still be used
    assert _refresh(client, tokens1["refresh_token"]).status_code == 401
    assert _refresh(client, tokens2["refresh_token"]).status_code == 401
