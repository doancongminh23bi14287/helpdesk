# backend/tests/test_ticket_delete.py
"""Tests for hard delete (permanent) ticket endpoint."""
import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_ticket(client, token, org_id, service_id, subject="Delete test"):
    r = client.post(
        "/api/tickets",
        json={"org_id": org_id, "service_id": service_id, "subject": subject},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


def set_status(client, token, ticket_id, status):
    """Chain valid transitions to reach the desired status."""
    # Valid transitions: Open→InProgress→Resolved→Closed
    chain = {
        "In Progress": ["In Progress"],
        "Resolved":    ["In Progress", "Resolved"],
        "Closed":      ["In Progress", "Resolved", "Closed"],
    }
    for s in chain.get(status, [status]):
        r = client.put(
            f"/api/tickets/{ticket_id}",
            json={"status": s},
            headers=auth(token),
        )
        assert r.status_code == 200, f"Failed to set status to {s}: {r.text}"


# ── Hard delete: happy paths ──────────────────────────────────────────────────

def test_hard_delete_resolved_ticket(
    client, admin_token, client_org, service
):
    ticket = create_ticket(client, admin_token, client_org.id, service.id)
    set_status(client, admin_token, ticket["id"], "Resolved")

    r = client.delete(f"/api/tickets/{ticket['id']}/permanent", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["deleted"] is True
    assert "freed_attachments" in data

    # Confirm ticket is gone
    r2 = client.get(f"/api/tickets/{ticket['id']}", headers=auth(admin_token))
    assert r2.status_code == 404


def test_hard_delete_closed_ticket(
    client, admin_token, client_org, service
):
    ticket = create_ticket(client, admin_token, client_org.id, service.id)
    set_status(client, admin_token, ticket["id"], "Closed")

    r = client.delete(f"/api/tickets/{ticket['id']}/permanent", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] is True


def test_hard_delete_soft_deleted_ticket(
    client, admin_token, client_org, service
):
    """Soft-deleted tickets (any status) can also be permanently deleted."""
    ticket = create_ticket(client, admin_token, client_org.id, service.id)

    # Soft delete first
    r_soft = client.delete(f"/api/tickets/{ticket['id']}", headers=auth(admin_token))
    assert r_soft.status_code == 200, r_soft.text

    # Hard delete
    r = client.delete(f"/api/tickets/{ticket['id']}/permanent", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] is True


# ── Hard delete: rejection paths ──────────────────────────────────────────────

def test_hard_delete_open_ticket_rejected(
    client, admin_token, client_org, service
):
    ticket = create_ticket(client, admin_token, client_org.id, service.id)
    # Status is Open by default

    r = client.delete(f"/api/tickets/{ticket['id']}/permanent", headers=auth(admin_token))
    assert r.status_code == 400, r.text
    assert "Resolved" in r.json()["detail"] or "Closed" in r.json()["detail"]


def test_hard_delete_in_progress_ticket_rejected(
    client, admin_token, client_org, service
):
    ticket = create_ticket(client, admin_token, client_org.id, service.id)
    set_status(client, admin_token, ticket["id"], "In Progress")

    r = client.delete(f"/api/tickets/{ticket['id']}/permanent", headers=auth(admin_token))
    assert r.status_code == 400, r.text


def test_hard_delete_non_admin_forbidden(
    client, customer_token, admin_token, client_org, service
):
    ticket = create_ticket(client, admin_token, client_org.id, service.id)
    set_status(client, admin_token, ticket["id"], "Resolved")

    r = client.delete(f"/api/tickets/{ticket['id']}/permanent", headers=auth(customer_token))
    assert r.status_code == 403, r.text


def test_hard_delete_nonexistent_ticket(
    client, admin_token
):
    r = client.delete("/api/tickets/999999/permanent", headers=auth(admin_token))
    assert r.status_code == 404, r.text


def test_hard_delete_cleans_email_log_and_threads(
    client, admin_token, client_org, service, db
):
    """email_log and email_threads have no CASCADE — explicit cleanup must prevent FK violation."""
    from app.models.notification import EmailLog
    from app.models.email_thread import EmailThread

    ticket = create_ticket(client, admin_token, client_org.id, service.id)
    tid = ticket["id"]
    set_status(client, admin_token, tid, "Resolved")

    # Simulate production data: email_log + email_threads rows for this ticket
    db.add(EmailLog(ticket_id=tid, action="outbound", detail="test email"))
    db.add(EmailThread(ticket_id=tid, direction="outbound"))
    db.commit()

    # Verify rows exist
    assert db.query(EmailLog).filter(EmailLog.ticket_id == tid).count() == 1
    assert db.query(EmailThread).filter(EmailThread.ticket_id == tid).count() == 1

    # Hard delete must succeed (was 500 FK violation before fix)
    r = client.delete(f"/api/tickets/{tid}/permanent", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] is True

    # Verify cleanup
    assert db.query(EmailLog).filter(EmailLog.ticket_id == tid).count() == 0
    assert db.query(EmailThread).filter(EmailThread.ticket_id == tid).count() == 0
