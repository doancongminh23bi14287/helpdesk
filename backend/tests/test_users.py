# backend/tests/test_users.py


def test_admin_can_list_all_users(client, admin_token, admin_user, customer_user):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    emails = [u["email"] for u in body["items"]]
    assert body["total"] >= 2
    assert "admin@test.com" in emails
    assert "customer@test.com" in emails


def test_customer_cannot_list_users(client, customer_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 403


def test_staff_cannot_list_users(client, staff_token):
    r = client.get("/api/users", headers={"Authorization": f"Bearer {staff_token}"})
    assert r.status_code == 403


def test_admin_can_create_user(client, admin_token, client_org):
    payload = {
        "email": "new@cty.vn",
        "password": "pass1234",
        "full_name": "New Person",
        "role": "customer",
        "org_id": client_org.id,
    }
    r = client.post("/api/users", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new@cty.vn"
    assert "password_hash" not in body  # never exposed


def test_create_user_duplicate_email_returns_409(client, admin_token, admin_user, provider_org):
    payload = {
        "email": "admin@test.com",  # already exists
        "password": "x",
        "full_name": "Dup",
        "role": "staff",
        "org_id": provider_org.id,
    }
    r = client.post("/api/users", json=payload,
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 409


def test_admin_can_update_user(client, admin_token, customer_user):
    r = client.put(f"/api/users/{customer_user.id}",
                   json={"full_name": "Updated Name"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated Name"


def test_update_nonexistent_user_returns_404(client, admin_token):
    r = client.put("/api/users/99999",
                   json={"full_name": "Ghost"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 404
