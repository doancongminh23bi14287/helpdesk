# backend/tests/test_security_features.py
"""
Security feature tests:
  - Token blacklist (deactivate/reactivate)
  - Login history recording
  - Force password change on new user / reset-password
"""

import pytest
from app.core.redis_client import redis_client
from app.models.login_history import LoginHistory


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _create_test_user(client, admin_token, client_org, email="testuser@example.com", password="pass1234"):
    r = client.post(
        "/api/users",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "role": "customer",
            "org_id": client_org.id,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Token Blacklist
# ─────────────────────────────────────────────────────────────────────────────

def test_deactivate_user_blacklists_token(client, admin_token, client_org):
    """Deactivating a user via PUT /api/users/{id} should immediately invalidate existing tokens."""
    user = _create_test_user(client, admin_token, client_org, email="blacklist_test@example.com")
    user_id = user["id"]

    try:
        # Login as the new user
        login_r = client.post("/api/auth/login", json={"email": "blacklist_test@example.com", "password": "pass1234"})
        assert login_r.status_code == 200, login_r.text
        access_token = login_r.json()["access_token"]

        # Verify token works
        me_r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me_r.status_code == 200, me_r.text

        # Admin deactivates the user
        deact_r = client.put(
            f"/api/users/{user_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert deact_r.status_code == 200, deact_r.text
        assert deact_r.json()["is_active"] is False

        # Old token should now be rejected
        blocked_r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert blocked_r.status_code == 401, f"Expected 401 but got {blocked_r.status_code}"
    finally:
        redis_client.delete(f"blacklist:user:{user_id}")


def test_reactivate_user_clears_blacklist(client, admin_token, client_org):
    """Reactivating a user removes the Redis blacklist entry and allows new logins."""
    user = _create_test_user(client, admin_token, client_org, email="reactivate_test@example.com")
    user_id = user["id"]

    try:
        # Login and get token
        login_r = client.post("/api/auth/login", json={"email": "reactivate_test@example.com", "password": "pass1234"})
        assert login_r.status_code == 200, login_r.text
        old_token = login_r.json()["access_token"]

        # Deactivate — blacklists old token
        client.put(
            f"/api/users/{user_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Confirm old token is blocked
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401

        # Reactivate
        react_r = client.put(
            f"/api/users/{user_id}",
            json={"is_active": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert react_r.status_code == 200, react_r.text
        assert react_r.json()["is_active"] is True

        # User can log in again and get a new token
        login2_r = client.post("/api/auth/login", json={"email": "reactivate_test@example.com", "password": "pass1234"})
        assert login2_r.status_code == 200, login2_r.text
        new_token = login2_r.json()["access_token"]

        # New token should work
        me_r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
        assert me_r.status_code == 200, me_r.text
    finally:
        redis_client.delete(f"blacklist:user:{user_id}")


def test_refresh_token_also_blocked_after_deactivate(client, admin_token, client_org):
    """After deactivation, the refresh token endpoint should also return 401."""
    user = _create_test_user(client, admin_token, client_org, email="refresh_block_test@example.com")
    user_id = user["id"]

    try:
        # Login — capture refresh token
        login_r = client.post("/api/auth/login", json={"email": "refresh_block_test@example.com", "password": "pass1234"})
        assert login_r.status_code == 200, login_r.text
        refresh_token = login_r.json()["refresh_token"]

        # Deactivate
        client.put(
            f"/api/users/{user_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Refresh should now be blocked
        ref_r = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert ref_r.status_code == 401, f"Expected 401 but got {ref_r.status_code}: {ref_r.text}"
    finally:
        redis_client.delete(f"blacklist:user:{user_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Login History
# ─────────────────────────────────────────────────────────────────────────────

def test_login_success_recorded(client, admin_user, db):
    """Successful login must create a LoginHistory row with status='success'."""
    client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})

    db.expire_all()
    rows = (
        db.query(LoginHistory)
        .filter(LoginHistory.email == "admin@test.com", LoginHistory.status == "success")
        .all()
    )
    assert len(rows) >= 1, "Expected at least one success login history row"


def test_login_failure_recorded(client, admin_user, db):
    """Failed login attempt (wrong password) must create a LoginHistory row with status='failed'."""
    client.post("/api/auth/login", json={"email": "admin@test.com", "password": "wrongpassword"})

    db.expire_all()
    rows = (
        db.query(LoginHistory)
        .filter(LoginHistory.email == "admin@test.com", LoginHistory.status == "failed")
        .all()
    )
    assert len(rows) >= 1, "Expected at least one failed login history row"


def test_login_blocked_recorded(client, admin_token, client_org, db):
    """Login attempt against a deactivated account must create a LoginHistory row with status='blocked'."""
    user = _create_test_user(client, admin_token, client_org, email="blocked_login_test@example.com")
    user_id = user["id"]

    try:
        # Deactivate user directly via DB (avoids touching tokens)
        from app.models.user import User
        db_user = db.query(User).filter(User.id == user_id).first()
        db_user.is_active = False
        db.commit()

        # Attempt login with deactivated account
        client.post("/api/auth/login", json={"email": "blocked_login_test@example.com", "password": "pass1234"})

        db.expire_all()
        rows = (
            db.query(LoginHistory)
            .filter(
                LoginHistory.email == "blocked_login_test@example.com",
                LoginHistory.status == "blocked",
            )
            .all()
        )
        assert len(rows) >= 1, "Expected at least one blocked login history row"
    finally:
        redis_client.delete(f"blacklist:user:{user_id}")


def test_admin_can_view_login_history(client, admin_user, admin_token):
    """Admin can view login history for any user."""
    # Login to produce at least one history entry
    client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})

    r = client.get(
        f"/api/users/{admin_user.id}/login-history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list), "Response should be a list"


def test_customer_cannot_view_login_history(client, admin_user, customer_token):
    """Non-admin users must be denied access to login history (403)."""
    r = client.get(
        f"/api/users/{admin_user.id}/login-history",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 403, f"Expected 403 but got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Force Password Change
# ─────────────────────────────────────────────────────────────────────────────

def test_new_user_has_must_change_password(client, admin_token, client_org):
    """Admin-created users must have must_change_password=True in the response."""
    user = _create_test_user(client, admin_token, client_org, email="mustchange_test@example.com")
    assert user["must_change_password"] is True, "New user should have must_change_password=True"


def test_change_password_clears_flag(client, admin_token, client_org):
    """Changing password clears the flag and revokes the old session token."""
    _create_test_user(client, admin_token, client_org, email="cp_test@example.com", password="pass1234")

    # Login as the new user
    login_r = client.post("/api/auth/login", json={"email": "cp_test@example.com", "password": "pass1234"})
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]

    # Change password
    cp_r = client.post(
        "/api/auth/change-password",
        json={"current_password": "pass1234", "new_password": "newpass999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cp_r.status_code == 200, cp_r.text

    # The password change revokes existing sessions, so the old token no longer works.
    me_r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_r.status_code == 401, me_r.text

    login2_r = client.post("/api/auth/login", json={"email": "cp_test@example.com", "password": "newpass999"})
    assert login2_r.status_code == 200, login2_r.text
    new_token = login2_r.json()["access_token"]

    me_r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_r.status_code == 200, me_r.text
    assert me_r.json()["must_change_password"] is False, "must_change_password should be False after password change"


def test_change_password_wrong_current_fails(client, admin_token, admin_user):
    """Providing the wrong current password to change-password must return 400."""
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "totallyWrong!", "new_password": "newpass999"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400, f"Expected 400 but got {r.status_code}: {r.text}"


def test_reset_password_sets_must_change_password(client, admin_token, client_org):
    """Admin reset-password must set must_change_password=True on the target user."""
    user = _create_test_user(client, admin_token, client_org, email="reset_pw_test@example.com", password="pass1234")
    user_id = user["id"]

    try:
        # Login as user and change password so must_change_password becomes False
        login_r = client.post("/api/auth/login", json={"email": "reset_pw_test@example.com", "password": "pass1234"})
        assert login_r.status_code == 200, login_r.text
        user_token = login_r.json()["access_token"]

        cp_r = client.post(
            "/api/auth/change-password",
            json={"current_password": "pass1234", "new_password": "changed999"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert cp_r.status_code == 200, cp_r.text

        # The old session is revoked by change-password; log in again to verify the flag.
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {user_token}"}).status_code == 401
        login2_r = client.post("/api/auth/login", json={"email": "reset_pw_test@example.com", "password": "changed999"})
        assert login2_r.status_code == 200, login2_r.text
        changed_token = login2_r.json()["access_token"]
        me_r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {changed_token}"})
        assert me_r.status_code == 200, me_r.text
        assert me_r.json()["must_change_password"] is False

        # Admin resets the password — this also blacklists existing tokens
        reset_r = client.post(
            f"/api/users/{user_id}/reset-password",
            json={"new_password": "adminreset1"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert reset_r.status_code == 200, reset_r.text
        assert reset_r.json()["must_change_password"] is True, "must_change_password should be True after admin reset"
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {changed_token}"}).status_code == 401
    finally:
        redis_client.delete(f"blacklist:user:{user_id}")
