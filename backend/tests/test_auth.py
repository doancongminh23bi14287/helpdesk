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


def test_rate_limit_triggers_after_10_login_attempts(client):
    """11th rapid login attempt from the same IP must return 429."""
    payload = {"email": "nobody@test.com", "password": "x"}
    for _ in range(10):
        client.post("/api/auth/login", json=payload)
    r = client.post("/api/auth/login", json=payload)
    assert r.status_code == 429


def test_failed_login_logged_to_history(client, admin_user, db):
    """Failed login (wrong password) must write a LoginHistory row with status='failed'."""
    from app.models.login_history import LoginHistory
    client.post("/api/auth/login", json={"email": "admin@test.com", "password": "wrongpass"})
    db.expire_all()
    rows = db.query(LoginHistory).filter(
        LoginHistory.email == "admin@test.com",
        LoginHistory.status == "failed",
    ).all()
    assert len(rows) >= 1


def test_security_headers_present(client):
    """All responses must include the required security headers."""
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-XSS-Protection") == "1; mode=block"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ── Profile + avatar ──────────────────────────────────────────────────────────
# libmagic identifies images by their leading signature plus structural markers.
# PNG_BYTES is a real 70-byte 1x1 PNG; JPEG_BYTES carries a JFIF header.
PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A"
    "0000000D49484452"
    "00000001000000010802000000907753DE"
    "0000000C49444154"
    "08D763F8CFC00000000300013600105D55"
    "0000000049454E44AE426082"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 200
SVG_BYTES = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" />'
TEXT_BYTES = b"hello world, this is plain text and definitely not an image"


def _isolate_avatar_storage(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "FILES_ROOT", str(tmp_path))


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_me_returns_avatar_fields(client, admin_token, admin_user):
    r = client.get("/api/auth/me", headers=_bearer(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "avatar_url" in body
    assert "avatar_color" in body
    assert body["avatar_url"] is None
    assert body["avatar_color"] is None
    # Internal field must not leak.
    assert "avatar_path" not in body
    assert "password_hash" not in body


def test_upload_png_avatar_sets_url(client, admin_token, admin_user, db, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    r = client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.png", PNG_BYTES, "image/png")},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # The returned URL must be a same-origin path the <img> tag can fetch
    # without an Authorization header.
    assert body["avatar_url"]
    assert body["avatar_url"].startswith(f"/api/auth/avatars/{admin_user.id}/")
    db.expire(admin_user)
    refreshed = db.get(admin_user.__class__, admin_user.id)
    assert refreshed.avatar_path and refreshed.avatar_path.startswith("avatars/")
    assert refreshed.avatar_mime_type == "image/png"
    assert refreshed.avatar_size_bytes == len(PNG_BYTES)


def test_public_avatar_route_serves_bytes_without_auth(client, admin_token, admin_user, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    up = client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.png", PNG_BYTES, "image/png")},
        headers=_bearer(admin_token),
    )
    avatar_url = up.json()["avatar_url"].split("?")[0]

    # No Authorization header — this is the whole point of the public route.
    r = client.get(avatar_url)
    assert r.status_code == 200, r.text
    assert r.content == PNG_BYTES
    assert r.headers.get("content-type", "").startswith("image/png")


def test_public_avatar_route_rejects_path_traversal(client, admin_user, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    r = client.get(f"/api/auth/avatars/{admin_user.id}/..%2Fsecret.png")
    # Either the route doesn't match (404 from router) or our DB lookup fails.
    assert r.status_code == 404


def test_public_avatar_route_404_when_filename_unknown(client, admin_user):
    r = client.get(f"/api/auth/avatars/{admin_user.id}/00000000.png")
    assert r.status_code == 404


def test_upload_jpeg_avatar_accepted(client, admin_token, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    r = client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.jpg", JPEG_BYTES, "image/jpeg")},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 200, r.text


def test_upload_unsupported_mime_rejected(client, admin_token, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    r = client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.svg", SVG_BYTES, "image/svg+xml")},
        headers=_bearer(admin_token),
    )
    assert r.status_code in (415, 422), r.text


def test_upload_text_disguised_as_png_rejected(client, admin_token, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    r = client.post(
        "/api/auth/me/avatar",
        files={"file": ("trick.png", TEXT_BYTES, "image/png")},
        headers=_bearer(admin_token),
    )
    # Either the magic check rejects the disguised content or the declared
    # type check does — both are correct outcomes; never 500, never 200.
    assert r.status_code in (415, 422), r.text


def test_upload_oversize_rejected(client, admin_token, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    # Real PNG header + padding past the 2 MB limit. Size check fires before magic.
    huge = PNG_BYTES + b"\x00" * (2 * 1024 * 1024 + 100)
    r = client.post(
        "/api/auth/me/avatar",
        files={"file": ("huge.png", huge, "image/png")},
        headers=_bearer(admin_token),
    )
    assert r.status_code in (413, 422), r.text


def test_unauthenticated_avatar_upload_rejected(client, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    r = client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.png", PNG_BYTES, "image/png")},
    )
    assert r.status_code == 401


def test_delete_avatar_clears_fields(client, admin_token, admin_user, db, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    up = client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.png", PNG_BYTES, "image/png")},
        headers=_bearer(admin_token),
    )
    assert up.status_code == 200

    rm = client.delete("/api/auth/me/avatar", headers=_bearer(admin_token))
    assert rm.status_code == 200, rm.text
    body = rm.json()
    assert body["avatar_url"] is None

    db.expire(admin_user)
    refreshed = db.get(admin_user.__class__, admin_user.id)
    assert refreshed.avatar_url is None
    assert refreshed.avatar_path is None
    assert refreshed.avatar_mime_type is None
    assert refreshed.avatar_size_bytes is None


def test_delete_avatar_preserves_color(client, admin_token, admin_user, db, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    client.patch("/api/auth/me", json={"avatar_color": "orange"}, headers=_bearer(admin_token))
    client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.png", PNG_BYTES, "image/png")},
        headers=_bearer(admin_token),
    )
    body = client.delete("/api/auth/me/avatar", headers=_bearer(admin_token)).json()
    assert body["avatar_color"] == "orange"


def test_patch_me_can_update_color_and_name(client, admin_token, admin_user, db):
    r = client.patch(
        "/api/auth/me",
        json={"full_name": "Updated Admin", "avatar_color": "blue", "phone": "+84 90 000 0000"},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Updated Admin"
    assert body["avatar_color"] == "blue"
    assert body["phone"] == "+84 90 000 0000"


def test_patch_me_cannot_escalate(client, admin_token, admin_user, db):
    """Email/role/org_id are not on UpdateMeRequest — server must reject the body."""
    r = client.patch(
        "/api/auth/me",
        json={"email": "attacker@evil.com", "role": "admin", "org_id": 999, "full_name": "OK"},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 422, r.text


def test_patch_me_rejects_bad_color(client, admin_token):
    r = client.patch(
        "/api/auth/me",
        json={"avatar_color": "neon_pink"},
        headers=_bearer(admin_token),
    )
    assert r.status_code == 422, r.text


def test_avatar_response_does_not_leak_internal_path(client, admin_token, admin_user, db, tmp_path, monkeypatch):
    _isolate_avatar_storage(tmp_path, monkeypatch)
    up = client.post(
        "/api/auth/me/avatar",
        files={"file": ("me.png", PNG_BYTES, "image/png")},
        headers=_bearer(admin_token),
    )
    body = up.json()
    assert "avatar_path" not in body
    assert "password_hash" not in body
