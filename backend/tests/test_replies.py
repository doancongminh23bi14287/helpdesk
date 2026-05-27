# backend/tests/test_replies.py
import pytest
from app.models.ticket import Ticket, TicketReply


# ── helpers ───────────────────────────────────────────────────────────────────

def make_ticket(db, client_org, service, customer_user, status="Open"):
    ticket = Ticket(
        org_id=client_org.id,
        service_id=service.id,
        subject="Test",
        status=status,
        raised_by=customer_user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


# ── tests ─────────────────────────────────────────────────────────────────────

def test_customer_can_add_reply(client, db, client_org, service, customer_user, customer_token):
    ticket = make_ticket(db, client_org, service, customer_user)
    r = client.post(
        f"/api/tickets/{ticket.id}/replies",
        json={"content": "Hello", "is_internal": False},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["content"] == "Hello"
    assert data["is_internal"] is False
    assert data["author_id"] == customer_user.id


def test_customer_reply_forces_is_internal_false(
    client, db, client_org, service, customer_user, customer_token
):
    ticket = make_ticket(db, client_org, service, customer_user)
    r = client.post(
        f"/api/tickets/{ticket.id}/replies",
        json={"content": "Try internal", "is_internal": True},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 201
    assert r.json()["is_internal"] is False


def test_staff_can_add_internal_reply(
    client, db, client_org, service, customer_user, staff_user, staff_token, staff_assignment
):
    ticket = make_ticket(db, client_org, service, customer_user)
    r = client.post(
        f"/api/tickets/{ticket.id}/replies",
        json={"content": "Staff note", "is_internal": True},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 201
    assert r.json()["is_internal"] is True


def test_list_replies_customer_sees_only_public(
    client, db, client_org, service, customer_user, staff_user, customer_token, staff_assignment
):
    ticket = make_ticket(db, client_org, service, customer_user)

    # Add one internal reply directly to DB
    internal_reply = TicketReply(
        ticket_id=ticket.id,
        author_id=staff_user.id,
        author_email=staff_user.email,
        content="Internal note",
        is_internal=True,
        source="portal",
    )
    # Add one public reply directly to DB
    public_reply = TicketReply(
        ticket_id=ticket.id,
        author_id=customer_user.id,
        author_email=customer_user.email,
        content="Public reply",
        is_internal=False,
        source="portal",
    )
    db.add(internal_reply)
    db.add(public_reply)
    db.commit()

    r = client.get(
        f"/api/tickets/{ticket.id}/replies",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["content"] == "Public reply"


def test_list_replies_staff_sees_all(
    client, db, client_org, service, customer_user, staff_user, staff_token, staff_assignment
):
    ticket = make_ticket(db, client_org, service, customer_user)

    internal_reply = TicketReply(
        ticket_id=ticket.id,
        author_id=staff_user.id,
        author_email=staff_user.email,
        content="Internal note",
        is_internal=True,
        source="portal",
    )
    public_reply = TicketReply(
        ticket_id=ticket.id,
        author_id=customer_user.id,
        author_email=customer_user.email,
        content="Public reply",
        is_internal=False,
        source="portal",
    )
    db.add(internal_reply)
    db.add(public_reply)
    db.commit()

    r = client.get(
        f"/api/tickets/{ticket.id}/replies",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_auto_reopen_waiting_on_customer_reply(
    client, db, client_org, service, customer_user, customer_token
):
    ticket = make_ticket(db, client_org, service, customer_user, status="Waiting")

    r = client.post(
        f"/api/tickets/{ticket.id}/replies",
        json={"content": "Following up", "is_internal": False},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 201

    # Check ticket status changed to In Progress
    detail_r = client.get(
        f"/api/tickets/{ticket.id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert detail_r.status_code == 200
    assert detail_r.json()["status"] == "In Progress"

    # Check activity with action=="status_change"
    activities = detail_r.json()["activities"]
    reopen_activities = [
        a for a in activities
        if a["action"] == "status_change"
        and a["from_value"] == "Waiting"
        and a["to_value"] == "In Progress"
    ]
    assert len(reopen_activities) == 1


def test_auto_reopen_resolved_on_customer_reply(
    client, db, client_org, service, customer_user, customer_token
):
    ticket = make_ticket(db, client_org, service, customer_user, status="Resolved")

    r = client.post(
        f"/api/tickets/{ticket.id}/replies",
        json={"content": "Not resolved yet", "is_internal": False},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 201

    detail_r = client.get(
        f"/api/tickets/{ticket.id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert detail_r.status_code == 200
    assert detail_r.json()["status"] == "In Progress"


def test_no_auto_reopen_on_staff_reply(
    client, db, client_org, service, customer_user, staff_user, staff_token, staff_assignment
):
    ticket = make_ticket(db, client_org, service, customer_user, status="Waiting")

    r = client.post(
        f"/api/tickets/{ticket.id}/replies",
        json={"content": "Staff checking in", "is_internal": False},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 201

    detail_r = client.get(
        f"/api/tickets/{ticket.id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert detail_r.status_code == 200
    assert detail_r.json()["status"] == "Waiting"


def test_reply_out_of_scope_returns_404(
    client, db, client_org, service, customer_user,
    second_customer_user, second_customer_token
):
    # Ticket belongs to client_org; second_customer_user is in second_client_org
    ticket = make_ticket(db, client_org, service, customer_user)

    r = client.post(
        f"/api/tickets/{ticket.id}/replies",
        json={"content": "Sneaky reply", "is_internal": False},
        headers={"Authorization": f"Bearer {second_customer_token}"},
    )
    assert r.status_code == 404
