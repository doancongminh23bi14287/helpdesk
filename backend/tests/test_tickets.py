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

def test_list_tickets_customer_sees_only_own_tickets(
    client, customer_token, admin_token, customer_user, client_org, second_client_org, service, db
):
    """Customer sees only their own tickets (raised_by == self AND org_id == own org)."""
    from app.models.service import Service

    svc2 = Service(org_id=second_client_org.id, name="Other SaaS", type="saas", status="active")
    db.add(svc2)
    db.commit()
    db.refresh(svc2)

    # Customer creates their own ticket in client_org — should be visible
    r1 = create_ticket(client, customer_token, client_org.id, service.id, "My ticket")
    assert r1.status_code == 201, r1.text

    # Admin creates a ticket in client_org — customer should NOT see it (raised_by != customer)
    r2 = create_ticket(client, admin_token, client_org.id, service.id, "Admin ticket same org")
    assert r2.status_code == 201, r2.text

    # Admin creates a ticket in another org — customer should NOT see it
    r3 = create_ticket(client, admin_token, second_client_org.id, svc2.id, "Ticket in org B")
    assert r3.status_code == 201, r3.text

    r = client.get("/api/tickets", headers=auth(customer_token))
    assert r.status_code == 200, r.text
    data = r.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["org_id"] == client_org.id
    assert items[0]["raised_by"] == customer_user.id


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
    assert r.json()["total"] == 2


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
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == open_id


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
    ids = [t["id"] for t in r.json()["items"]]
    assert tid not in ids


def test_soft_delete_customer_forbidden(
    client, customer_token, admin_token, client_org, service
):
    r = create_ticket(client, admin_token, client_org.id, service.id, "Cannot Delete")
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.delete(f"/api/tickets/{tid}", headers=auth(customer_token))
    assert r.status_code == 403, r.text


def test_soft_delete_staff_forbidden(client, db, staff_token, staff_assignment, service):
    # staff_assignment gives staff_user access to client_org
    # Create a ticket in client_org first (use admin_token via fixture... but we need admin_user)
    # Simpler: create ticket directly in DB
    from app.models.ticket import Ticket
    ticket = Ticket(org_id=service.org_id, service_id=service.id, subject="Staff del test", status="Open")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    r = client.delete(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {staff_token}"})
    assert r.status_code == 403


def test_update_ticket_out_of_scope_returns_404(client, db, staff_token, second_client_org):
    # Create a ticket in second_client_org (staff is NOT assigned there)
    from app.models.ticket import Ticket
    ticket = Ticket(org_id=second_client_org.id, subject="Other org ticket", status="Open")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    r = client.put(f"/api/tickets/{ticket.id}", json={"status": "In Progress"},
                   headers={"Authorization": f"Bearer {staff_token}"})
    assert r.status_code == 404


def test_update_priority_logs_activity(client, db, admin_token, admin_user, client_org, service):
    # Create ticket
    from app.models.ticket import Ticket
    ticket = Ticket(org_id=client_org.id, service_id=service.id, subject="Priority test", status="Open", priority="Medium")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    r = client.put(f"/api/tickets/{ticket.id}", json={"priority": "High"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    # Check activity logged
    detail = client.get(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {admin_token}"})
    activities = detail.json()["activities"]
    priority_changes = [a for a in activities if a["action"] == "priority_change"]
    assert len(priority_changes) == 1
    assert priority_changes[0]["from_value"] == "Medium"
    assert priority_changes[0]["to_value"] == "High"


def test_update_assignee_logs_activity(client, db, admin_token, admin_user, staff_user, client_org, service):
    from app.models.ticket import Ticket
    ticket = Ticket(org_id=client_org.id, service_id=service.id, subject="Assign test", status="Open")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    r = client.put(f"/api/tickets/{ticket.id}", json={"assignee_id": staff_user.id},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    detail = client.get(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {admin_token}"})
    activities = detail.json()["activities"]
    assign_logs = [a for a in activities if a["action"] == "assigned"]
    assert len(assign_logs) == 1
    assert assign_logs[0]["to_value"] == str(staff_user.id)


def test_create_ticket_default_priority_and_type(client, db, customer_token, client_org, service):
    r = client.post("/api/tickets",
                    json={"org_id": client_org.id, "service_id": service.id, "subject": "Defaults test"},
                    headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 201
    assert r.json()["priority"] == "Medium"
    assert r.json()["ticket_type"] == "Question"


def test_customer_cannot_see_internal_replies(client, db, customer_token, admin_token, customer_user, client_org, service):
    from app.models.ticket import Ticket, TicketReply
    ticket = Ticket(org_id=client_org.id, service_id=service.id, subject="Internal reply test",
                    status="Open", raised_by=customer_user.id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    # Add internal reply directly
    internal_reply = TicketReply(ticket_id=ticket.id, content="Internal note", is_internal=True, source="portal")
    public_reply = TicketReply(ticket_id=ticket.id, content="Public reply", is_internal=False, source="portal")
    db.add(internal_reply)
    db.add(public_reply)
    db.commit()
    # Customer GET detail — should only see public reply
    r = client.get(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 200
    replies = r.json()["replies"]
    assert len(replies) == 1
    assert replies[0]["content"] == "Public reply"
    # Admin sees both
    r2 = client.get(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert len(r2.json()["replies"]) == 2


# ── TICKET TYPE VALIDATION ───────────────────────────────────────────────────
# Regression: previously POST /api/tickets with ticket_type="support" returned 500
# because the value was passed straight through to MariaDB whose enum rejected it.
# Invalid values must now be rejected at the schema layer with 422.

ALLOWED_TICKET_TYPES = [
    "Question",
    "Bug",
    "Incident",
    "Task Request",
    "Change Request",
    "Feature Request",
    "Content Request",
    "SEO Request",
    "Approval Required",
    "Complaint",
    "Renewal",
    "Other",
]


@pytest.mark.parametrize("ticket_type", ALLOWED_TICKET_TYPES)
def test_create_ticket_accepts_valid_ticket_type(
    client, customer_token, client_org, service, ticket_type
):
    r = create_ticket(
        client, customer_token, client_org.id, service.id,
        f"Valid type {ticket_type}", ticket_type=ticket_type,
    )
    assert r.status_code == 201, r.text
    assert r.json()["ticket_type"] == ticket_type


@pytest.mark.parametrize(
    "bad_type",
    ["support", "URGENT_BUG", "bug", "question", "random", "Unspecified", "Service SaaS", "Service Hosting"],
)
def test_create_ticket_rejects_invalid_ticket_type(
    client, db, customer_token, client_org, service, bad_type
):
    from app.models.ticket import Ticket
    before = db.query(Ticket).count()
    r = create_ticket(
        client, customer_token, client_org.id, service.id,
        "Bad type ticket", ticket_type=bad_type,
    )
    assert r.status_code == 422, r.text
    after = db.query(Ticket).count()
    assert after == before


def test_create_ticket_empty_ticket_type_defaults_to_question(
    client, customer_token, client_org, service
):
    """Empty/blank ticket_type normalises to 'Question' (default)."""
    r = create_ticket(
        client, customer_token, client_org.id, service.id,
        "Blank type", ticket_type="",
    )
    assert r.status_code == 201, r.text
    assert r.json()["ticket_type"] == "Question"
