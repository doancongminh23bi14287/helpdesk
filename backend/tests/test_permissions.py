# backend/tests/test_permissions.py


def test_unauthenticated_request_returns_401(client):
    r = client.get("/api/organizations")
    assert r.status_code == 401


def test_admin_can_reach_admin_only_endpoint(client, admin_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    # 200 or 404 are both fine — we just need NOT 403
    assert r.status_code != 403


def test_customer_cannot_reach_admin_only_endpoint(client, customer_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 403


def test_staff_cannot_reach_admin_only_endpoint(client, staff_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {staff_token}"})
    assert r.status_code == 403
