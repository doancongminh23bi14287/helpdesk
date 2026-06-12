# backend/tests/test_phase5a.py
"""
Phase 5A tests: Contact CRUD, Address CRUD, Item CRUD,
and current item-based subscription pricing.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_item(client, admin_token, code="SVC-001", unit_price=500000):
    r = client.post(
        "/api/items",
        json={"code": code, "name": f"Item {code}", "type": "saas",
              "unit_price": unit_price, "unit": "month"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()

# ─────────────────────────────────────────────────────────────────────────────
# Contact CRUD
# ─────────────────────────────────────────────────────────────────────────────

def test_admin_can_list_contacts(client, admin_token, db, client_org):
    from app.models.contact import Contact
    contact = Contact(org_id=client_org.id, name="Alice", role="primary",
                      email="alice@example.com", phone="0901234567")
    db.add(contact)
    db.commit()

    r = client.get(
        f"/api/organizations/{client_org.id}/contacts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    names = [c["name"] for c in r.json()]
    assert "Alice" in names


def test_admin_can_create_contact(client, admin_token, db, client_org):
    r = client.post(
        f"/api/organizations/{client_org.id}/contacts",
        json={"name": "Bob", "role": "billing", "email": "bob@example.com",
              "phone": "0909090909"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "Bob"
    assert data["role"] == "billing"
    assert data["email"] == "bob@example.com"
    assert data["org_id"] == client_org.id


def test_admin_can_update_contact(client, admin_token, db, client_org):
    from app.models.contact import Contact
    contact = Contact(org_id=client_org.id, name="Carol", role="primary")
    db.add(contact)
    db.commit()
    db.refresh(contact)

    r = client.put(
        f"/api/organizations/{client_org.id}/contacts/{contact.id}",
        json={"name": "Carol Updated", "role": "technical"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "Carol Updated"
    assert data["role"] == "technical"


def test_admin_can_delete_contact(client, admin_token, db, client_org):
    from app.models.contact import Contact
    contact = Contact(org_id=client_org.id, name="Dave", role="other")
    db.add(contact)
    db.commit()
    db.refresh(contact)

    r = client.delete(
        f"/api/organizations/{client_org.id}/contacts/{contact.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text

    r = client.get(
        f"/api/organizations/{client_org.id}/contacts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_customer_can_read_own_org_contacts(client, customer_token, db,
                                             client_org, customer_user):
    from app.models.contact import Contact
    contact = Contact(org_id=client_org.id, name="Eve", role="primary")
    db.add(contact)
    db.commit()

    r = client.get(
        f"/api/organizations/{client_org.id}/contacts",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 200, r.text
    names = [c["name"] for c in r.json()]
    assert "Eve" in names


def test_customer_cannot_read_other_org_contacts(client, second_customer_token,
                                                  db, client_org):
    r = client.get(
        f"/api/organizations/{client_org.id}/contacts",
        headers={"Authorization": f"Bearer {second_customer_token}"},
    )
    assert r.status_code == 404, r.text


def test_non_admin_cannot_create_contact(client, customer_token, db, client_org):
    r = client.post(
        f"/api/organizations/{client_org.id}/contacts",
        json={"name": "Hacker", "role": "primary"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────────────────────
# Address CRUD
# ─────────────────────────────────────────────────────────────────────────────

def test_admin_can_list_addresses(client, admin_token, db, client_org):
    from app.models.address import Address
    addr = Address(org_id=client_org.id, label="HQ", street="123 Main St",
                   city="Hanoi", country="Vietnam")
    db.add(addr)
    db.commit()

    r = client.get(
        f"/api/organizations/{client_org.id}/addresses",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    labels = [a["label"] for a in r.json()]
    assert "HQ" in labels


def test_admin_can_create_address(client, admin_token, db, client_org):
    r = client.post(
        f"/api/organizations/{client_org.id}/addresses",
        json={"label": "Branch", "street": "456 Side St",
              "city": "Ho Chi Minh City", "country": "Vietnam"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["label"] == "Branch"
    assert data["city"] == "Ho Chi Minh City"
    assert data["org_id"] == client_org.id


def test_admin_can_delete_address(client, admin_token, db, client_org):
    from app.models.address import Address
    addr = Address(org_id=client_org.id, label="Old Office", country="Vietnam")
    db.add(addr)
    db.commit()
    db.refresh(addr)

    r = client.delete(
        f"/api/organizations/{client_org.id}/addresses/{addr.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text


def test_customer_cannot_read_other_org_addresses(client, second_customer_token,
                                                   db, client_org):
    r = client.get(
        f"/api/organizations/{client_org.id}/addresses",
        headers={"Authorization": f"Bearer {second_customer_token}"},
    )
    assert r.status_code == 404, r.text


# ─────────────────────────────────────────────────────────────────────────────
# Item CRUD
# ─────────────────────────────────────────────────────────────────────────────

def test_admin_can_create_item(client, admin_token):
    r = client.post(
        "/api/items",
        json={"code": "ITEM-001", "name": "SaaS Item", "type": "saas",
              "unit_price": 500000, "unit": "month"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["code"] == "ITEM-001"
    assert data["name"] == "SaaS Item"


def test_duplicate_item_code_returns_409(client, admin_token, db):
    _make_item(client, admin_token, code="DUP-001")
    r = client.post(
        "/api/items",
        json={"code": "DUP-001", "name": "Duplicate", "type": "saas",
              "unit_price": 100000, "unit": "month"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409, r.text


def test_list_items_returns_active_only(client, admin_token, db):
    from app.models.item import Item
    active_item = Item(code="ACTIVE-001", name="Active Item", type="saas",
                       unit_price=100000, unit="month", is_active=True)
    inactive_item = Item(code="INACTIVE-001", name="Inactive Item", type="saas",
                         unit_price=100000, unit="month", is_active=False)
    db.add(active_item)
    db.add(inactive_item)
    db.commit()

    r = client.get("/api/items", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    codes = [i["code"] for i in r.json()]
    assert "ACTIVE-001" in codes
    assert "INACTIVE-001" not in codes


def test_customer_can_list_items(client, customer_token):
    r = client.get("/api/items", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 200, r.text


def test_admin_can_update_item(client, admin_token, db):
    item = _make_item(client, admin_token, code="UPD-001")
    item_id = item["id"]

    r = client.put(
        f"/api/items/{item_id}",
        json={"name": "Updated Name"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Updated Name"


def test_get_item_by_id(client, admin_token, db):
    item = _make_item(client, admin_token, code="GET-001")
    item_id = item["id"]

    r = client.get(
        f"/api/items/{item_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == item_id
    assert data["code"] == "GET-001"


# ─────────────────────────────────────────────────────────────────────────────
# Item list/update/delete contracts
# ─────────────────────────────────────────────────────────────────────────────

def test_items_paginated_search_returns_contract(client, admin_token):
    item = _make_item(client, admin_token, code="SEARCH-001", unit_price=450000)

    r = client.get(
        "/api/items?paginated=true&search=SEARCH-001",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert {"items", "total", "page", "per_page"}.issubset(data.keys())
    assert any(i["id"] == item["id"] for i in data["items"])


def test_admin_can_update_item_unit_price(client, admin_token):
    item = _make_item(client, admin_token, code="PRICE-UPD-001")

    new_price = 399000
    r = client.put(
        f"/api/items/{item['id']}",
        json={"unit_price": new_price},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert float(r.json()["unit_price"]) == float(new_price)


def test_admin_can_soft_delete_item(client, admin_token):
    item = _make_item(client, admin_token, code="ITEM-DEL-001")

    r = client.delete(
        f"/api/items/{item['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text

    r = client.get("/api/items", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert all(i["id"] != item["id"] for i in r.json())

    r = client.get(
        "/api/items?paginated=true&is_active=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert any(i["id"] == item["id"] for i in r.json()["items"])


def test_deleted_item_detail_still_readable_for_admin(client, admin_token):
    item = _make_item(client, admin_token, code="ITEM-READ-DELETED-001")

    r = client.delete(
        f"/api/items/{item['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text

    r = client.get(
        f"/api/items/{item['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == item["id"]
    assert r.json()["is_active"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Current item-based subscription pricing
# ─────────────────────────────────────────────────────────────────────────────

def test_subscription_uses_item_base_price(
        client, admin_token, db, client_org):
    item = _make_item(client, admin_token, code="LOOK-001", unit_price=500000)

    r = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": item["id"], "start_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["item_id"] == item["id"]
    assert float(data["unit_price"]) == 500000.0


def test_subscription_monthly_price_uses_item_price(
        client, admin_token, db, client_org):
    item = _make_item(client, admin_token, code="LOOK-MONTH-001", unit_price=500000)

    r = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item["id"],
            "start_date": "2024-01-01",
            "billing_cycle": "monthly",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    assert float(r.json()["unit_price"]) == 500000.0


def test_subscription_quarterly_cycle_discount(client, admin_token, db, client_org):
    base_price = 500000
    item = _make_item(client, admin_token, code="DISC-Q-001", unit_price=base_price)

    r = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item["id"],
            "start_date": "2024-01-01",
            "billing_cycle": "quarterly",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    assert float(r.json()["unit_price"]) == 1425000.0


def test_subscription_yearly_cycle_discount(client, admin_token, db, client_org):
    base_price = 500000
    item = _make_item(client, admin_token, code="DISC-Y-001", unit_price=base_price)

    r = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item["id"],
            "start_date": "2024-01-01",
            "billing_cycle": "yearly",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    assert float(r.json()["unit_price"]) == 4800000.0


def test_customer_cannot_create_item(client, customer_token):
    r = client.post(
        "/api/items",
        json={"code": "NOPE-001", "name": "Nope", "type": "saas",
              "unit_price": 100000, "unit": "month"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 403, r.text


def test_subscription_rejects_missing_item(client, admin_token, db, client_org):
    r = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": 999999, "start_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400, r.text


def test_subscription_create_stores_due_days_and_tax_rate(client, admin_token, db, client_org):
    item = _make_item(client, admin_token, code="SUB-TAX-001", unit_price=500000)

    r = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item["id"],
            "start_date": "2024-01-01",
            "due_days": 30,
            "tax_rate": 8.5,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["due_days"] == 30
    assert float(data["tax_rate"]) == 8.5
