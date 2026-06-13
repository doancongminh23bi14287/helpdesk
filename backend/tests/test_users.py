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


def test_delete_user_success(client, admin_token, db, client_org):
    """Deleting a user with no tickets returns 204."""
    from app.models.user import User
    from app.core.security import hash_password
    victim = User(
        org_id=client_org.id,
        email="victim_delete@test.com",
        password_hash=hash_password("pass"),
        full_name="Victim",
        role="customer",
        is_active=True,
    )
    db.add(victim)
    db.commit()
    db.refresh(victim)
    resp = client.delete(f"/api/users/{victim.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 204


def test_delete_user_409_when_has_tickets(client, admin_token, db, client_org):
    """Deleting a user with tickets (as raised_by) returns 409."""
    from app.models.user import User
    from app.models.ticket import Ticket
    from app.core.security import hash_password
    victim = User(
        org_id=client_org.id,
        email="victim_409@test.com",
        password_hash=hash_password("pass"),
        full_name="Victim409",
        role="customer",
        is_active=True,
    )
    db.add(victim)
    db.commit()
    db.refresh(victim)
    t = Ticket(
        org_id=client_org.id,
        raised_by=victim.id,
        raised_by_email=victim.email,
        subject="Blocking ticket",
        status="Open",
        priority="Medium",
        ticket_type="Question",
    )
    db.add(t)
    db.commit()
    resp = client.delete(f"/api/users/{victim.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 409
    assert "ticket" in resp.json()["detail"].lower()


def test_delete_user_409_when_is_assignee(client, admin_token, db, client_org, staff_user):
    """Deleting a user who is an assignee on a ticket returns 409 (not 500)."""
    from app.models.user import User
    from app.models.ticket import Ticket
    from app.core.security import hash_password
    reporter = User(
        org_id=client_org.id,
        email="reporter_assignee@test.com",
        password_hash=hash_password("pass"),
        full_name="Reporter",
        role="customer",
        is_active=True,
    )
    db.add(reporter)
    db.commit()
    db.refresh(reporter)
    t = Ticket(
        org_id=client_org.id,
        raised_by=reporter.id,
        raised_by_email=reporter.email,
        subject="Assignee blocking ticket",
        status="Open",
        priority="Medium",
        ticket_type="Question",
        assignee_id=staff_user.id,
    )
    db.add(t)
    db.commit()
    resp = client.delete(f"/api/users/{staff_user.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 409
    assert "ticket" in resp.json()["detail"].lower()
