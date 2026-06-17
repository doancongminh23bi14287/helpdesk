"""Tests for Sprint E: unified project discussion endpoint."""
import time
import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_project(db, org_id, created_by, name="Discussion Project"):
    from app.models.project import Project
    p = Project(
        org_id=org_id,
        name=name,
        project_type="seo",
        status="open",
        visibility="customer_visible",
        created_by=created_by,
        progress_percent=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_ticket(db, org_id, project_id, raised_by, subject="Test Ticket", status="Open"):
    from app.models.ticket import Ticket
    t = Ticket(
        org_id=org_id,
        project_id=project_id,
        subject=subject,
        status=status,
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by=raised_by,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_reply(db, ticket_id, author_id, content, is_internal=False):
    from app.models.ticket import TicketReply
    r = TicketReply(
        ticket_id=ticket_id,
        author_id=author_id,
        content=content,
        is_internal=is_internal,
        source="portal",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ── E.1 GET /api/projects/{id}/discussion ────────────────────────────────────

def test_discussion_merges_replies_from_multiple_tickets(
    client, db, admin_token, admin_user, client_org
):
    """Replies from 2 tickets merge into 1 sorted timeline."""
    project = _make_project(db, client_org.id, admin_user.id)
    t1 = _make_ticket(db, client_org.id, project.id, admin_user.id, subject="Ticket Alpha")
    t2 = _make_ticket(db, client_org.id, project.id, admin_user.id, subject="Ticket Beta")

    r1 = _make_reply(db, t1.id, admin_user.id, "Reply on ticket 1")
    r2 = _make_reply(db, t2.id, admin_user.id, "Reply on ticket 2")

    resp = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # sorted ASC — r1 was created first
    assert data["items"][0]["id"] == r1.id
    assert data["items"][1]["id"] == r2.id
    # ticket metadata enriched
    assert data["items"][0]["ticket_subject"] == "Ticket Alpha"
    assert data["items"][1]["ticket_subject"] == "Ticket Beta"


def test_discussion_customer_cannot_see_internal_replies(
    client, db, admin_token, customer_token, admin_user, customer_user, client_org
):
    """Customer cannot see is_internal=True replies."""
    project = _make_project(db, client_org.id, admin_user.id)
    ticket = _make_ticket(db, client_org.id, project.id, admin_user.id)

    _make_reply(db, ticket.id, admin_user.id, "Public reply", is_internal=False)
    _make_reply(db, ticket.id, admin_user.id, "Internal secret", is_internal=True)

    # Staff sees both
    staff_resp = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(admin_token))
    assert staff_resp.json()["total"] == 2

    # Customer sees only public
    cust_resp = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(customer_token))
    assert cust_resp.status_code == 200, cust_resp.text
    data = cust_resp.json()
    assert data["total"] == 1
    assert data["items"][0]["content"] == "Public reply"
    assert not data["items"][0]["is_internal"]


def test_discussion_staff_sees_internal_replies(
    client, db, admin_token, admin_user, client_org
):
    """Staff can see is_internal=True replies."""
    project = _make_project(db, client_org.id, admin_user.id)
    ticket = _make_ticket(db, client_org.id, project.id, admin_user.id)

    _make_reply(db, ticket.id, admin_user.id, "Internal only", is_internal=True)

    resp = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["is_internal"] is True


def test_discussion_reply_enriched_with_author_name(
    client, db, admin_token, admin_user, client_org
):
    """Each reply has author_name resolved from users table."""
    project = _make_project(db, client_org.id, admin_user.id)
    ticket = _make_ticket(db, client_org.id, project.id, admin_user.id)
    _make_reply(db, ticket.id, admin_user.id, "Hello world")

    resp = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(admin_token))
    item = resp.json()["items"][0]
    assert item["author_name"] == admin_user.full_name
    assert item["ticket_subject"] == ticket.subject


def test_discussion_pagination(
    client, db, admin_token, admin_user, client_org
):
    """?page=1&per_page=2 returns exactly 2 items, total reflects all."""
    project = _make_project(db, client_org.id, admin_user.id)
    ticket = _make_ticket(db, client_org.id, project.id, admin_user.id)

    for i in range(5):
        _make_reply(db, ticket.id, admin_user.id, f"Reply {i}")

    resp = client.get(
        f"/api/projects/{project.id}/discussion",
        params={"page": 1, "per_page": 2},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["items"][0]["content"] == "Reply 0"
    assert data["items"][1]["content"] == "Reply 1"


def test_discussion_empty_when_no_tickets(
    client, db, admin_token, admin_user, client_org
):
    """Project with no linked tickets returns total=0, items=[]."""
    project = _make_project(db, client_org.id, admin_user.id)
    resp = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == {"total": 0, "items": []}


# ── E.1 POST /api/projects/{id}/discussion ────────────────────────────────────

def test_post_discussion_creates_reply_on_primary_ticket(
    client, db, admin_token, admin_user, client_org
):
    """POST creates a TicketReply on the oldest open ticket."""
    project = _make_project(db, client_org.id, admin_user.id)
    t_old = _make_ticket(db, client_org.id, project.id, admin_user.id, subject="Older Ticket")
    t_new = _make_ticket(db, client_org.id, project.id, admin_user.id, subject="Newer Ticket")

    resp = client.post(
        f"/api/projects/{project.id}/discussion",
        json={"content": "Hello from project", "is_internal": False},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["ticket_id"] == t_old.id
    assert data["ticket_subject"] == "Older Ticket"
    assert data["content"] == "Hello from project"
    assert data["author_name"] == admin_user.full_name


def test_post_discussion_409_when_no_open_ticket(
    client, db, admin_token, admin_user, client_org
):
    """POST returns 409 when all linked tickets are Closed/Resolved."""
    project = _make_project(db, client_org.id, admin_user.id)
    _make_ticket(db, client_org.id, project.id, admin_user.id, status="Closed")

    resp = client.post(
        f"/api/projects/{project.id}/discussion",
        json={"content": "Try to post"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409
    assert "No open ticket" in resp.json()["detail"]


def test_post_discussion_customer_cannot_set_internal(
    client, db, customer_token, admin_user, customer_user, client_org
):
    """Customer's is_internal=True is silently overridden to False."""
    project = _make_project(db, client_org.id, admin_user.id)
    _make_ticket(db, client_org.id, project.id, customer_user.id)

    resp = client.post(
        f"/api/projects/{project.id}/discussion",
        json={"content": "Sneaky internal", "is_internal": True},
        headers=_auth(customer_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_internal"] is False
