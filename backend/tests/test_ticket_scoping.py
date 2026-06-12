# backend/tests/test_ticket_scoping.py
"""
Ticket visibility scoping tests.

Rules under test:
- Admin: sees ALL tickets.
- Staff: sees ticket if (org_id IN assigned orgs) OR (assignee_id == self).
- Customer: sees ticket ONLY if raised_by == self AND org_id == own org.
- is_internal replies: never visible to customers; always visible to staff/admin.
"""
import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_ticket(client, token, org_id, service_id, subject="Test ticket"):
    r = client.post("/api/tickets", json={
        "org_id": org_id,
        "service_id": service_id,
        "subject": subject,
    }, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Staff org-assignment scoping ──────────────────────────────────────────────

@pytest.fixture
def org_a(db):
    from app.models.organization import Organization
    org = Organization(name="Org A", code="ORG-A-SCOPE", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def org_b(db):
    from app.models.organization import Organization
    org = Organization(name="Org B", code="ORG-B-SCOPE", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def svc_a(db, org_a):
    from app.models.service import Service
    svc = Service(org_id=org_a.id, name="Svc A", type="saas", status="active")
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@pytest.fixture
def svc_b(db, org_b):
    from app.models.service import Service
    svc = Service(org_id=org_b.id, name="Svc B", type="saas", status="active")
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@pytest.fixture
def provider_org_for_scoping(db):
    from app.models.organization import Organization
    org = Organization(name="Provider Scoping", code="PROV-SCOPE", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_staff(db, provider_org, suffix):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        org_id=provider_org.id,
        email=f"staff_{suffix}@scope-test.com",
        password_hash=hash_password("pass123"),
        full_name=f"Staff {suffix}",
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_customer(db, org, suffix):
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        org_id=org.id,
        email=f"cust_{suffix}@scope-test.com",
        password_hash=hash_password("pass123"),
        full_name=f"Customer {suffix}",
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _assign_staff_to_org(db, staff, org):
    from app.models.team import StaffOrgAssignment
    row = StaffOrgAssignment(user_id=staff.id, org_id=org.id)
    db.add(row)
    db.commit()


def _token(client, email, password="pass123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_staff_assigned_to_org_sees_its_tickets(
    client, db, admin_token, org_a, svc_a, provider_org_for_scoping
):
    """Staff assigned to org A can list and GET org A tickets."""
    staff = _make_staff(db, provider_org_for_scoping, "s1")
    _assign_staff_to_org(db, staff, org_a)
    tok = _token(client, staff.email)

    tid = _make_ticket(client, admin_token, org_a.id, svc_a.id, "Org A ticket")

    r = client.get("/api/tickets", headers=auth(tok))
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()["items"]]
    assert tid in ids, "Staff should see org A ticket"

    r2 = client.get(f"/api/tickets/{tid}", headers=auth(tok))
    assert r2.status_code == 200


def test_staff_not_assigned_to_org_cannot_see_its_tickets(
    client, db, admin_token, org_a, org_b, svc_a, svc_b, provider_org_for_scoping
):
    """Staff assigned ONLY to org B cannot see org A tickets."""
    staff = _make_staff(db, provider_org_for_scoping, "s2")
    _assign_staff_to_org(db, staff, org_b)  # only org B
    tok = _token(client, staff.email)

    tid = _make_ticket(client, admin_token, org_a.id, svc_a.id, "Org A ticket")

    # List: ticket should not appear
    r = client.get("/api/tickets", headers=auth(tok))
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()["items"]]
    assert tid not in ids, "Staff should NOT see org A ticket"

    # Detail: should 404
    r2 = client.get(f"/api/tickets/{tid}", headers=auth(tok))
    assert r2.status_code == 404


def test_staff_sees_directly_assigned_ticket_regardless_of_org(
    client, db, admin_token, org_a, org_b, svc_a, provider_org_for_scoping
):
    """Staff not assigned to org A but directly set as assignee can see the ticket."""
    staff = _make_staff(db, provider_org_for_scoping, "s3")
    _assign_staff_to_org(db, staff, org_b)  # only org B
    tok = _token(client, staff.email)

    # Admin creates ticket in org A and assigns it to staff
    r = client.post("/api/tickets", json={
        "org_id": org_a.id,
        "service_id": svc_a.id,
        "subject": "Directly assigned ticket",
        "assignee_id": staff.id,
    }, headers=auth(admin_token))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    # Staff should see it even though org A is not in their assignments
    r2 = client.get(f"/api/tickets/{tid}", headers=auth(tok))
    assert r2.status_code == 200

    r3 = client.get("/api/tickets", headers=auth(tok))
    ids = [t["id"] for t in r3.json()["items"]]
    assert tid in ids


# ── Customer scoping (raised_by) ──────────────────────────────────────────────

def test_customer_sees_only_own_tickets_not_all_org_tickets(
    client, db, admin_token, org_a, svc_a
):
    """Customer sees only tickets THEY raised, not all tickets in their org."""
    cust = _make_customer(db, org_a, "c1")
    tok = _token(client, cust.email)

    # Ticket created by admin in org_a — customer should NOT see it
    admin_tid = _make_ticket(client, admin_token, org_a.id, svc_a.id, "Admin's ticket")

    # Ticket created by customer — should see it
    my_tid = _make_ticket(client, tok, org_a.id, svc_a.id, "My ticket")

    r = client.get("/api/tickets", headers=auth(tok))
    assert r.status_code == 200
    items = r.json()["items"]
    ids = [t["id"] for t in items]
    assert my_tid in ids
    assert admin_tid not in ids, "Customer must not see tickets raised by others"


def test_customer_cannot_get_ticket_raised_by_other_user_same_org(
    client, db, org_a, svc_a
):
    """Two customers in the same org cannot see each other's tickets."""
    cust1 = _make_customer(db, org_a, "c2a")
    cust2 = _make_customer(db, org_a, "c2b")
    tok1 = _token(client, cust1.email)
    tok2 = _token(client, cust2.email)

    tid = _make_ticket(client, tok1, org_a.id, svc_a.id, "Cust1 ticket")

    r = client.get(f"/api/tickets/{tid}", headers=auth(tok2))
    assert r.status_code == 404, "Customer 2 must not see customer 1's ticket"


# ── Internal notes visibility ─────────────────────────────────────────────────

def test_customer_cannot_see_internal_replies_via_list_endpoint(
    client, db, admin_token, org_a, svc_a
):
    """GET /replies as customer returns only is_internal=False replies."""
    cust = _make_customer(db, org_a, "c3")
    tok = _token(client, cust.email)

    tid = _make_ticket(client, tok, org_a.id, svc_a.id, "My support ticket")

    # Admin posts a public reply
    client.post(f"/api/tickets/{tid}/replies",
        json={"content": "Public reply", "is_internal": False},
        headers=auth(admin_token))

    # Admin posts an internal note
    client.post(f"/api/tickets/{tid}/replies",
        json={"content": "Internal note", "is_internal": True},
        headers=auth(admin_token))

    r = client.get(f"/api/tickets/{tid}/replies", headers=auth(tok))
    assert r.status_code == 200
    replies = r.json()
    internal = [rep for rep in replies if rep.get("is_internal")]
    assert not internal, f"Customer must not see internal replies, got {len(internal)}"
    assert len(replies) == 1
    assert replies[0]["content"] == "Public reply"


def test_customer_cannot_see_internal_replies_via_detail_endpoint(
    client, db, admin_token, org_a, svc_a
):
    """GET /api/tickets/{id} must not include internal replies for customers."""
    cust = _make_customer(db, org_a, "c3detail")
    tok = _token(client, cust.email)

    tid = _make_ticket(client, tok, org_a.id, svc_a.id, "My support ticket detail")

    client.post(
        f"/api/tickets/{tid}/replies",
        json={"content": "Public detail reply", "is_internal": False},
        headers=auth(admin_token),
    )
    client.post(
        f"/api/tickets/{tid}/replies",
        json={"content": "Internal detail note", "is_internal": True},
        headers=auth(admin_token),
    )

    r = client.get(f"/api/tickets/{tid}", headers=auth(tok))
    assert r.status_code == 200
    replies = r.json()["replies"]
    assert [rep["content"] for rep in replies] == ["Public detail reply"]
    assert all(rep["is_internal"] is False for rep in replies)


def test_staff_can_see_internal_replies_for_their_org_tickets(
    client, db, admin_token, org_a, svc_a, provider_org_for_scoping
):
    """Staff assigned to org A can see is_internal replies on org A tickets."""
    staff = _make_staff(db, provider_org_for_scoping, "s4")
    _assign_staff_to_org(db, staff, org_a)
    tok = _token(client, staff.email)

    tid = _make_ticket(client, admin_token, org_a.id, svc_a.id, "Staff-visible ticket")

    client.post(f"/api/tickets/{tid}/replies",
        json={"content": "Staff-only note", "is_internal": True},
        headers=auth(admin_token))

    r = client.get(f"/api/tickets/{tid}/replies", headers=auth(tok))
    assert r.status_code == 200
    replies = r.json()
    internal = [rep for rep in replies if rep.get("is_internal")]
    assert len(internal) == 1, "Staff must see internal replies for their tickets"


def test_customer_reply_is_always_public(
    client, db, admin_token, org_a, svc_a
):
    """Customer POSTing is_internal=True has it silently overridden to False."""
    cust = _make_customer(db, org_a, "c4")
    tok = _token(client, cust.email)

    tid = _make_ticket(client, tok, org_a.id, svc_a.id, "My ticket")

    r = client.post(f"/api/tickets/{tid}/replies",
        json={"content": "Trying to be internal", "is_internal": True},
        headers=auth(tok))
    assert r.status_code == 201
    assert r.json()["is_internal"] is False, "Customer reply must never be internal"
