"""
Tests for /api/seo/gsc endpoints.

Google API calls are fully mocked — no real network requests.
Covers: status, scoping, search-analytics-without-connection,
callback state validation, and disconnect.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.models.gsc_connection import GscConnection


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def gsc_conn(db, client_org, admin_user):
    """A GscConnection for client_org."""
    conn = GscConnection(
        org_id=client_org.id,
        refresh_token="test-refresh-token",
        access_token="test-access-token",
        token_expiry=datetime.utcnow() + timedelta(hours=1),
        connected_by=admin_user.id,
        status="connected",
        property_url=None,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@pytest.fixture
def staff_token_assigned(client, staff_user, client_org, db):
    """Staff user assigned to client_org."""
    from app.models.team import StaffOrgAssignment
    db.add(StaffOrgAssignment(user_id=staff_user.id, org_id=client_org.id))
    db.commit()
    r = client.post("/api/auth/login", json={"email": "staff@test.com", "password": "staff123"})
    return r.json()["access_token"]


# ── /status ───────────────────────────────────────────────────────────────────

def test_status_no_connection(client, admin_token, client_org):
    r = client.get(
        f"/api/seo/gsc/status?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is False
    assert data["org_id"] == client_org.id


def test_status_with_connection(client, admin_token, client_org, gsc_conn, admin_user):
    r = client.get(
        f"/api/seo/gsc/status?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is True
    assert data["org_id"] == client_org.id
    assert data["status"] == "connected"
    # tokens must NEVER appear in status response
    assert "access_token" not in data
    assert "refresh_token" not in data


def test_status_defaults_to_own_org(client, admin_token, admin_user, provider_org, gsc_conn, client_org, db):
    """Admin without ?org_id sees their own org (provider_org), not client_org."""
    r = client.get(
        "/api/seo/gsc/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    # admin_user belongs to provider_org which has no connection
    assert data["org_id"] == provider_org.id
    assert data["connected"] is False


# ── scoping ───────────────────────────────────────────────────────────────────

def test_status_staff_cannot_see_unassigned_org(client, staff_token, client_org, gsc_conn):
    """Staff not assigned to client_org must get 404 (assert_org_access)."""
    r = client.get(
        f"/api/seo/gsc/status?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 404


def test_status_staff_can_see_assigned_org(client, staff_token_assigned, client_org, gsc_conn):
    r = client.get(
        f"/api/seo/gsc/status?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {staff_token_assigned}"},
    )
    assert r.status_code == 200
    assert r.json()["connected"] is True


def test_status_customer_forbidden(client, customer_token, client_org, gsc_conn):
    """Customers cannot access GSC endpoints at all."""
    r = client.get(
        f"/api/seo/gsc/status?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 403


def test_property_cross_org_blocked(client, staff_token, client_org, gsc_conn):
    """Staff not assigned to client_org cannot set its GSC property."""
    r = client.post(
        f"/api/seo/gsc/property?org_id={client_org.id}",
        json={"property_url": "sc-domain:evil.com"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 404


def test_search_analytics_cross_org_blocked(client, staff_token, client_org, gsc_conn, db):
    """Staff not assigned to client_org cannot read its search analytics."""
    gsc_conn.property_url = "sc-domain:example.com"
    db.commit()
    r = client.get(
        f"/api/seo/gsc/search-analytics?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 404


def test_disconnect_cross_org_blocked(client, staff_token, client_org, gsc_conn):
    """Staff not assigned to client_org cannot disconnect its GSC connection."""
    r = client.post(
        f"/api/seo/gsc/disconnect?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 404


# ── /search-analytics without connection ──────────────────────────────────────

def test_search_analytics_no_connection(client, admin_token, client_org):
    r = client.get(
        f"/api/seo/gsc/search-analytics?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
    assert "No GSC connection" in r.json()["detail"]


def test_search_analytics_no_property_selected(client, admin_token, client_org, gsc_conn):
    """Connection exists but no property_url set → 400."""
    r = client.get(
        f"/api/seo/gsc/search-analytics?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400
    assert "No property selected" in r.json()["detail"]


def test_search_analytics_with_property_mocked(client, admin_token, client_org, gsc_conn, db):
    """With property set + mocked GSC API, returns data from Google."""
    gsc_conn.property_url = "sc-domain:example.com"
    db.commit()

    mock_response = {
        "rows": [
            {"keys": ["seo agency"], "clicks": 120, "impressions": 3000, "ctr": 0.04, "position": 5.2},
        ]
    }

    with patch("app.services.gsc.get_valid_token", return_value="fake-token"), \
         patch("app.services.gsc.query_search_analytics", return_value=mock_response):
        r = client.get(
            f"/api/seo/gsc/search-analytics?org_id={client_org.id}&dimensions=query",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    assert data["rows"][0]["clicks"] == 120


# ── /properties mocked ────────────────────────────────────────────────────────

def test_list_properties_mocked(client, admin_token, client_org, gsc_conn):
    mock_sites = [
        {"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"},
        {"siteUrl": "https://example.com/", "permissionLevel": "siteFullUser"},
    ]

    with patch("app.services.gsc.get_valid_token", return_value="fake-token"), \
         patch("app.services.gsc.list_sites", return_value=mock_sites):
        r = client.get(
            f"/api/seo/gsc/properties?org_id={client_org.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert r.status_code == 200
    assert len(r.json()["properties"]) == 2


# ── /property POST ────────────────────────────────────────────────────────────

def test_select_property(client, admin_token, client_org, gsc_conn):
    r = client.post(
        f"/api/seo/gsc/property?org_id={client_org.id}",
        json={"property_url": "sc-domain:example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["property_url"] == "sc-domain:example.com"


# ── /callback CSRF validation ─────────────────────────────────────────────────

def test_callback_invalid_state_redirects_with_error(client):
    r = client.get("/api/seo/gsc/callback?code=abc&state=bad-state", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "gsc_error=invalid_state" in r.headers["location"]


def test_callback_error_param_redirects(client):
    r = client.get("/api/seo/gsc/callback?error=access_denied", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "gsc_error=access_denied" in r.headers["location"]


def test_callback_missing_code_redirects(client):
    r = client.get("/api/seo/gsc/callback?state=somestate", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "gsc_error" in r.headers["location"]


def test_callback_valid_state_creates_connection(client, db, client_org, admin_user):
    """Valid state in Redis → token exchange → connection created in DB."""
    from app.core.redis_client import redis_client

    state = "test-valid-state-12345"
    redis_client.setex(f"gsc_state:{state}", 600, f"{client_org.id}:{admin_user.id}")

    mock_tokens = {
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
        "expires_in": 3600,
    }

    with patch("app.services.gsc.exchange_code", return_value=mock_tokens):
        r = client.get(
            f"/api/seo/gsc/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

    assert r.status_code in (302, 307)
    assert "gsc_connected=1" in r.headers["location"]

    conn = db.query(GscConnection).filter(GscConnection.org_id == client_org.id).first()
    assert conn is not None
    assert conn.refresh_token == "new-refresh-token"
    assert conn.status == "connected"


# ── /disconnect ───────────────────────────────────────────────────────────────

def test_disconnect_removes_connection(client, admin_token, client_org, gsc_conn, db):
    with patch("app.services.gsc.revoke_token"):
        r = client.post(
            f"/api/seo/gsc/disconnect?org_id={client_org.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    assert r.json()["disconnected"] is True

    remaining = db.query(GscConnection).filter(GscConnection.org_id == client_org.id).first()
    assert remaining is None


def test_disconnect_no_connection_returns_404(client, admin_token, client_org):
    r = client.post(
        f"/api/seo/gsc/disconnect?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


# ── /connect endpoint ─────────────────────────────────────────────────────────

def test_connect_unconfigured_returns_503(client, admin_token, client_org):
    """When GSC_CLIENT_ID is empty, endpoint returns 503."""
    import app.config as cfg
    original_id = cfg.GSC_CLIENT_ID
    original_secret = cfg.GSC_CLIENT_SECRET
    try:
        cfg.GSC_CLIENT_ID = ""
        cfg.GSC_CLIENT_SECRET = ""
        r = client.get(
            f"/api/seo/gsc/connect?org_id={client_org.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 503
    finally:
        cfg.GSC_CLIENT_ID = original_id
        cfg.GSC_CLIENT_SECRET = original_secret


def test_connect_configured_returns_url(client, admin_token, client_org):
    """With credentials set, returns a Google auth URL."""
    import app.config as cfg
    original_id = cfg.GSC_CLIENT_ID
    original_secret = cfg.GSC_CLIENT_SECRET
    try:
        cfg.GSC_CLIENT_ID = "fake-client-id.apps.googleusercontent.com"
        cfg.GSC_CLIENT_SECRET = "fake-secret"
        r = client.get(
            f"/api/seo/gsc/connect?org_id={client_org.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "url" in data
        assert "accounts.google.com" in data["url"]
        assert "webmasters.readonly" in data["url"]
    finally:
        cfg.GSC_CLIENT_ID = original_id
        cfg.GSC_CLIENT_SECRET = original_secret
