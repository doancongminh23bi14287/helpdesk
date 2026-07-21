from datetime import datetime, timedelta
from unittest.mock import patch

from app.services.seo_security import new_oauth_state
from app.models.gsc_connection import GscConnection
from app.models.ga4_connection import Ga4Connection

class RedisState:
    def __init__(self, value): self.value = value
    def getdel(self, key): value, self.value = self.value, None; return value

def test_gsc_callback_creates_connection_after_provider_metadata(client_org, admin_user, db):
    state, payload = new_oauth_state("gsc", admin_user.id, client_org.id)
    redis = RedisState(payload)
    with patch("app.api.seo_gsc.redis_client", redis), patch("app.services.gsc.exchange_code", return_value={"access_token": "A", "refresh_token": "R", "expires_in": 3600}), patch("app.services.gsc.list_sites", return_value=[{"siteUrl": "https://example.com"}]), patch("app.api.seo_gsc.config.FRONTEND_URL", "http://localhost:5173"):
        from app.api.seo_gsc import oauth_callback
        response = oauth_callback(code="AUTH", state=state, error=None, db=db)
    assert response.status_code in (302, 307)
    conn = db.query(GscConnection).filter_by(org_id=client_org.id).one()
    assert conn.connected_by == admin_user.id
    assert "A" not in response.headers["location"] and "AUTH" not in response.headers["location"]
    assert redis.value is None

def test_ga4_provider_failure_consumes_state_without_connection(client_org, admin_user, db):
    state, payload = new_oauth_state("ga4", admin_user.id, client_org.id)
    redis = RedisState(payload)
    with patch("app.api.seo_ga4.redis_client", redis), patch("app.services.ga4.exchange_code", side_effect=TimeoutError("provider sentinel")):
        from app.api.seo_ga4 import oauth_callback
        response = oauth_callback(code="AUTH", state=state, error=None, db=db)
    assert response.status_code in (302, 307)
    assert db.query(Ga4Connection).filter_by(org_id=client_org.id).count() == 0
    assert redis.value is None
    assert "AUTH" not in response.headers["location"]


def test_existing_gsc_connection_survives_property_failure_in_new_session(client_org, admin_user, db):
    old = GscConnection(org_id=client_org.id, refresh_token="OLD_REFRESH_TOKEN", access_token="OLD_ACCESS_TOKEN",
                        token_expiry=datetime.utcnow() + timedelta(hours=1), property_url="https://old.example",
                        connected_by=admin_user.id, status="connected")
    db.add(old); db.commit()
    state, payload = new_oauth_state("gsc", admin_user.id, client_org.id)
    redis = RedisState(payload)
    with patch("app.api.seo_gsc.redis_client", redis), patch("app.services.gsc.exchange_code", return_value={"access_token": "NEW_ACCESS", "refresh_token": "NEW_REFRESH"}), patch("app.services.gsc.list_sites", side_effect=TimeoutError("RAW_PROVIDER_SENTINEL")):
        from app.api.seo_gsc import oauth_callback
        response = oauth_callback(code="AUTH_CODE_SENTINEL", state=state, error=None, db=db)
    from tests.conftest import TestingSessionLocal
    fresh = TestingSessionLocal()
    try:
        saved = fresh.query(GscConnection).filter_by(org_id=client_org.id).one()
        assert (saved.access_token, saved.refresh_token, saved.property_url, saved.status) == ("OLD_ACCESS_TOKEN", "OLD_REFRESH_TOKEN", "https://old.example", "connected")
    finally:
        fresh.close()
    location = response.headers["location"]
    assert "AUTH_CODE_SENTINEL" not in location and "RAW_PROVIDER_SENTINEL" not in location


def test_existing_ga4_refresh_token_is_preserved_when_provider_omits_replacement(client_org, admin_user, db):
    old = Ga4Connection(org_id=client_org.id, refresh_token="OLD_REFRESH_TOKEN", access_token="OLD_ACCESS_TOKEN",
                        property_id="111", property_name="Old", connected_by=admin_user.id, status="connected")
    db.add(old); db.commit()
    state, payload = new_oauth_state("ga4", admin_user.id, client_org.id)
    redis = RedisState(payload)
    with patch("app.api.seo_ga4.redis_client", redis), patch("app.services.ga4.exchange_code", return_value={"access_token": "NEW_ACCESS", "expires_in": 3600}), patch("app.services.ga4.list_properties", return_value=[{"property": "properties/222", "displayName": "New"}]):
        from app.api.seo_ga4 import oauth_callback
        response = oauth_callback(code="AUTH", state=state, error=None, db=db)
    from tests.conftest import TestingSessionLocal
    fresh = TestingSessionLocal()
    try:
        saved = fresh.query(Ga4Connection).filter_by(org_id=client_org.id).one()
        assert saved.refresh_token == "OLD_REFRESH_TOKEN"
        assert saved.access_token == "NEW_ACCESS"
    finally:
        fresh.close()
    assert "NEW_ACCESS" not in response.headers["location"]
