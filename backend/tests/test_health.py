# backend/tests/test_health.py
def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_docs_accessible(client):
    r = client.get("/docs")
    assert r.status_code == 200
