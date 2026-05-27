# backend/tests/test_auth.py


def test_login_returns_tokens(client, admin_user):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client, admin_user):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email_returns_401(client):
    r = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r.status_code == 401


def test_refresh_returns_new_access_token(client, admin_user):
    login = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    refresh_token = login.json()["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_me_returns_current_user(client, admin_token, admin_user):
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "admin@test.com"
    assert body["role"] == "admin"


def test_me_without_token_returns_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_logout_returns_200(client, admin_token):
    r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
