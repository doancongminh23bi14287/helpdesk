# backend/tests/test_ticket_archive.py
"""
Customer personal-archive tests.

Rules under test:
- Archiving hides the ticket from the customer's default list (archived=false).
- ?archived=true returns only archived tickets, still scoped to the customer.
- Unarchive restores the ticket to the default list.
- Only the ticket creator (customer) may archive; staff/admin get 403.
- Staff/admin ticket lists are unaffected by the flag.
"""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_ticket(client, token, org_id, subject="Archive test"):
    r = client.post("/api/tickets", json={
        "org_id": org_id,
        "subject": subject,
    }, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _list_ids(client, token, **params):
    r = client.get("/api/tickets", params=params, headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    return [t["id"] for t in items]


def test_archive_hides_from_default_list(client, customer_token, customer_user, client_org):
    tid = _make_ticket(client, customer_token, client_org.id)
    assert tid in _list_ids(client, customer_token)

    r = client.put(f"/api/tickets/{tid}/archive", headers=auth(customer_token))
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is True

    assert tid not in _list_ids(client, customer_token)
    assert tid in _list_ids(client, customer_token, archived=True)


def test_unarchive_restores_to_default_list(client, customer_token, client_org):
    tid = _make_ticket(client, customer_token, client_org.id)
    client.put(f"/api/tickets/{tid}/archive", headers=auth(customer_token))

    r = client.put(f"/api/tickets/{tid}/unarchive", headers=auth(customer_token))
    assert r.status_code == 200, r.text
    assert r.json()["archived"] is False

    assert tid in _list_ids(client, customer_token)
    assert tid not in _list_ids(client, customer_token, archived=True)


def test_archived_ticket_still_accessible_directly(client, customer_token, client_org):
    tid = _make_ticket(client, customer_token, client_org.id)
    client.put(f"/api/tickets/{tid}/archive", headers=auth(customer_token))

    r = client.get(f"/api/tickets/{tid}", headers=auth(customer_token))
    assert r.status_code == 200, r.text


def test_admin_cannot_archive_and_list_unaffected(client, admin_token, customer_token, client_org):
    tid = _make_ticket(client, customer_token, client_org.id)

    r = client.put(f"/api/tickets/{tid}/archive", headers=auth(admin_token))
    assert r.status_code == 403, r.text

    # Customer archives it; admin still sees it in the default list
    client.put(f"/api/tickets/{tid}/archive", headers=auth(customer_token))
    assert tid in _list_ids(client, admin_token)
