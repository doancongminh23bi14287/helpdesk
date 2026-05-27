# backend/tests/test_tickets.py
"""Phase 2 — Ticket CRUD tests (TDD: write first, implement second)."""
import pytest


# ── Helper ────────────────────────────────────────────────────────────────────

def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_ticket(client, token, org_id, service_id, subject="Help", **kwargs):
    payload = {"org_id": org_id, "service_id": service_id, "subject": subject}
    payload.update(kwargs)
    return client.post("/api/tickets", json=payload, headers=auth(token))


# ── CREATE ────────────────────────────────────────────────────────────────────

def test_create_ticket_defaults_to_open(
    client, customer_token, customer_user, client_org, service
):
    r = create_ticket(client, customer_token, client_org.id, service.id, "Help")
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "Open"
    assert data["source"] == "portal"
    assert data["raised_by"] == customer_user.id


def test_create_ticket_service_must_belong_to_org(
    client, admin_token, client_org, second_client_org, service, db
):
    """service belongs to client_org; posting with second_client_org.id should fail."""
    from app.models.service import Service
    other_service = Service(org_id=second_client_org.id, name="Other SaaS", type="saas", status="active")
    db.add(other_service)
    db.commit()
    db.refresh(other_service)

    # service.id belongs to client_org, but we pass second_client_org.id — admin bypasses org check
    r = create_ticket(client, admin_token, second_client_org.id, service.id, "Help")
    assert r.status_code in (400, 422), r.text


def test_create_ticket_customer_cannot_use_other_org(
    client, customer_token, second_client_org, service
):
    """Customer from client_org tries to create a ticket under second_client_org."""
    r = create_ticket(client, customer_token, second_client_org.id, service.id, "Help")
    # 403 because the org_id != user.org_id — checked before FK validation
    assert r.status_code in (400, 403, 422), r.text
    # Strictly should be 403
    assert r.status_code == 403, r.text


# ── LIST ─────────────────────────────────────────────────────────────────────

def test_list_tickets_customer_sees_only_own_org(
    client, customer_token, admin_token, client_org, second_client_org, service, db
):
    """Customer from client_org should only see tickets in their org."""
    from app.models.service import Service

    # Create service for second_client_org
    svc2 = Service(org_id=second_client_org.id, name="Other SaaS", type="saas", status="active")
    db.add(svc2)
    db.commit()
    db.refresh(svc2)

    # Admin creates one ticket in client_org and one in second_client_org
    r1 = create_ticket(client, admin_token, client_org.id, service.id, "Ticket in org A")
    assert r1.status_code == 201, r1.text

    r2 = create_ticket(client, admin_token, second_client_org.id, svc2.id, "Ticket in org B")
    assert r2.status_code == 201, r2.text

    r = client.get("/api/tickets", headers=auth(customer_token))
    assert r.status_code == 200, r.text
    tickets = r.json()
    assert len(tickets) == 1
    assert tickets[0]["org_id"] == client_org.id


def test_list_tickets_admin_sees_all(
    client, admin_token, client_org, second_client_org, service, db
):
    from app.models.service import Service

    svc2 = Service(org_id=second_client_org.id, name="Other SaaS", type="saas", status="active")
    db.add(svc2)
    db.commit()
    db.refresh(svc2)

    r1 = create_ticket(client, admin_token, client_org.id, service.id, "Ticket A")
    assert r1.status_code == 201, r1.text
    r2 = create_ticket(client, admin_token, second_client_org.id, svc2.id, "Ticket B")
    assert r2.status_code == 201, r2.text

    r = client.get("/api/tickets", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert len(r.json()) == 2


def test_list_tickets_filter_by_status(
    client, admin_token, staff_token, client_org, service, staff_assignment
):
    """Create one Open + one Resolved ticket; filter by status=Open."""
    # Create open ticket
    r1 = create_ticket(client, admin_token, client_org.id, service.id, "Open Ticket")
    assert r1.status_code == 201, r1.text
    open_id = r1.json()["id"]

    # Create a second ticket and advance it to Resolved via valid transitions
    r2 = create_ticket(client, admin_token, client_org.id, service.id, "Resolved Ticket")
    assert r2.status_code == 201, r2.text
    t2_id = r2.json()["id"]

    # Open -> In Progress -> Resolved
    r = client.put(f"/api/tickets/{t2_id}", json={"status": "In Progress"}, headers=auth(staff_token))
    assert r.status_code == 200, r.text
    r = client.put(f"/api/tickets/{t2_id}", json={"status": "Resolved"}, headers=auth(staff_token))
    assert r.status_code == 200, r.text

    r = client.get("/api/tickets?status=Open", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    tickets = r.json()
    assert len(tickets) == 1
    assert tickets[0]["id"] == open_id


# ── DETAIL ────────────────────────────────────────────────────────────────────

def test_get_ticket_detail(
    client, customer_token, customer_user, client_org, service
):
    r = create_ticket(client, customer_token, client_org.id, service.id, "Need Help")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.get(f"/api/tickets/{tid}", headers=auth(customer_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["subject"] == "Need Help"
    assert data["replies"] == []
    activities = data["activities"]
    assert len(activities) >= 1
    assert any(a["action"] == "created" for a in activities)


def test_get_ticket_out_of_scope_returns_404(
    client, customer_token, admin_token, second_client_org, db
):
    """Customer from client_org tries GET on a ticket belonging to second_client_org."""
    from app.models.service import Service

    svc2 = Service(org_id=second_client_org.id, name="Other SaaS", type="saas", status="active")
    db.add(svc2)
    db.commit()
    db.refresh(svc2)

    r = create_ticket(client, admin_token, second_client_org.id, svc2.id, "Other Org Ticket")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.get(f"/api/tickets/{tid}", headers=auth(customer_token))
    assert r.status_code == 404, r.text


# ── UPDATE ────────────────────────────────────────────────────────────────────

def test_staff_update_status_open_to_in_progress(
    client, staff_token, admin_token, client_org, service, staff_assignment
):
    r = create_ticket(client, admin_token, client_org.id, service.id, "Need Staff Help")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.put(
        f"/api/tickets/{tid}",
        json={"status": "In Progress"},
        headers=auth(staff_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "In Progress"

    r = client.get(f"/api/tickets/{tid}", headers=auth(staff_token))
    assert r.status_code == 200, r.text
    activities = r.json()["activities"]
    status_change = [a for a in activities if a["action"] == "status_change"]
    assert len(status_change) == 1
    assert status_change[0]["from_value"] == "Open"
    assert status_change[0]["to_value"] == "In Progress"


def test_invalid_status_transition(
    client, staff_token, admin_token, client_org, service, staff_assignment
):
    """Open -> Closed is invalid per state machine."""
    r = create_ticket(client, admin_token, client_org.id, service.id, "Invalid Transition")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.put(
        f"/api/tickets/{tid}",
        json={"status": "Closed"},
        headers=auth(staff_token),
    )
    assert r.status_code in (400, 422), r.text


def test_customer_cannot_update_status(
    client, customer_token, admin_token, client_org, service
):
    r = create_ticket(client, admin_token, client_org.id, service.id, "Customer Ticket")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.put(
        f"/api/tickets/{tid}",
        json={"status": "In Progress"},
        headers=auth(customer_token),
    )
    assert r.status_code == 403, r.text


# ── SOFT DELETE ───────────────────────────────────────────────────────────────

def test_soft_delete_admin_only(
    client, admin_token, client_org, service
):
    r = create_ticket(client, admin_token, client_org.id, service.id, "Delete Me")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.delete(f"/api/tickets/{tid}", headers=auth(admin_token))
    assert r.status_code == 200, r.text

    r = client.get("/api/tickets", headers=auth(admin_token))
    ids = [t["id"] for t in r.json()]
    assert tid not in ids


def test_soft_delete_customer_forbidden(
    client, customer_token, admin_token, client_org, service
):
    r = create_ticket(client, admin_token, client_org.id, service.id, "Cannot Delete")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.delete(f"/api/tickets/{tid}", headers=auth(customer_token))
    assert r.status_code == 403, r.text
