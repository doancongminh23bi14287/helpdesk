# backend/tests/test_organizations.py
from app.models.service import Service


def test_admin_can_list_all_orgs(client, admin_token, client_org, provider_org):
    r = client.get("/api/organizations", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    ids = [o["id"] for o in body["items"]]
    assert body["total"] >= 2
    assert client_org.id in ids
    assert provider_org.id in ids


def test_customer_sees_only_own_org(client, customer_token, customer_user, client_org, provider_org):
    r = client.get("/api/organizations", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()["items"]]
    assert ids == [client_org.id]
    assert provider_org.id not in ids


def test_admin_can_create_org(client, admin_token):
    payload = {"name": "New Corp", "code": "NEW-CORP", "status": "active"}
    r = client.post("/api/organizations", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["code"] == "NEW-CORP"


def test_create_org_with_duplicate_code_returns_409(client, admin_token, client_org):
    payload = {"name": "Dup", "code": client_org.code, "status": "active"}
    r = client.post("/api/organizations", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 409


def test_customer_cannot_create_org(client, customer_token):
    r = client.post("/api/organizations",
                    json={"name": "X", "code": "X-001", "status": "active"},
                    headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 403


def test_get_org_detail(client, admin_token, client_org):
    r = client.get(f"/api/organizations/{client_org.id}",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["id"] == client_org.id


def test_customer_cannot_view_other_org(client, customer_token, provider_org):
    r = client.get(f"/api/organizations/{provider_org.id}",
                   headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 404


def test_admin_can_update_org(client, admin_token, client_org):
    r = client.put(f"/api/organizations/{client_org.id}",
                   json={"phone": "0901234567"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["phone"] == "0901234567"


def test_get_org_services(client, admin_token, client_org, db):
    svc = Service(org_id=client_org.id, type="saas", name="Test SaaS", status="active")
    db.add(svc)
    db.commit()
    r = client.get(f"/api/organizations/{client_org.id}/services",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert any(s["name"] == "Test SaaS" for s in r.json())


def test_unauthenticated_list_orgs_returns_401(client):
    r = client.get("/api/organizations")
    assert r.status_code == 401
