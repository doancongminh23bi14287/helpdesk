# backend/tests/test_health.py
from unittest.mock import patch


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "CustomerHub API"
    assert body["version"] == "1.0.0"
    assert "timestamp" in body


def test_docs_accessible(client):
    r = client.get("/docs")
    assert r.status_code == 200


def test_ready_returns_ok_when_all_deps_healthy(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"
    assert body["checks"]["email_outbox"].startswith("ok")
    assert "timestamp" in body


def test_ready_returns_503_when_db_down(client, db):
    from sqlalchemy.exc import OperationalError

    # The client fixture injects `db` via dependency override.
    # Patching db.execute on that same session object makes /ready see a DB failure.
    with patch.object(db, "execute", side_effect=OperationalError("DB down", {}, None)):
        r = client.get("/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert "error" in body["checks"]["database"]


def test_ready_returns_503_when_redis_down(client):
    # Patch the ping method on the actual Redis instance that app.main holds.
    from app.core.redis_client import redis_client as real_redis
    with patch.object(real_redis, "ping", side_effect=ConnectionError("Redis unreachable")):
        r = client.get("/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert "error" in body["checks"]["redis"]


def test_metrics_smoke(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_requests_total" in body
    assert "email_outbox_pending_count" in body
