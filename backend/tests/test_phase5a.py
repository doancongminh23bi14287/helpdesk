# backend/tests/test_phase5a.py
"""
Phase 5A tests: Contact CRUD, Address CRUD, Item CRUD,
Price List management, and Price resolution.
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


def _make_price_list(client, admin_token, name="Test PL"):
    r = client.post(
        "/api/price-lists",
        json={"name": name, "currency": "VND"},
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
    assert r.status_code == 403, r.text


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
    assert r.status_code == 403, r.text


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
# Price List with items
# ─────────────────────────────────────────────────────────────────────────────

def test_admin_can_create_price_list(client, admin_token):
    r = client.post(
        "/api/price-lists",
        json={"name": "Standard PL", "currency": "VND"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "Standard PL"
    assert data["currency"] == "VND"


def test_admin_can_add_item_to_price_list(client, admin_token, db):
    item = _make_item(client, admin_token, code="PLI-001")
    pl = _make_price_list(client, admin_token, name="PL With Items")

    r = client.post(
        f"/api/price-lists/{pl['id']}/items",
        json={"item_id": item["id"], "unit_price": 450000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["item_id"] == item["id"]
    assert float(data["unit_price"]) == 450000.0


def test_get_price_list_detail_includes_items(client, admin_token, db):
    item = _make_item(client, admin_token, code="PLI-DET-001")
    pl = _make_price_list(client, admin_token, name="PL Detail")

    # Add item to price list
    r = client.post(
        f"/api/price-lists/{pl['id']}/items",
        json={"item_id": item["id"], "unit_price": 420000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text

    # Fetch detail
    r = client.get(
        f"/api/price-lists/{pl['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["items"]) == 1
    pl_item = data["items"][0]
    assert pl_item["item_id"] == item["id"]
    assert pl_item["item"] is not None
    assert pl_item["item"]["code"] == "PLI-DET-001"


def test_admin_can_update_price_list_item(client, admin_token, db):
    item = _make_item(client, admin_token, code="PLI-UPD-001")
    pl = _make_price_list(client, admin_token, name="PL Update")

    client.post(
        f"/api/price-lists/{pl['id']}/items",
        json={"item_id": item["id"], "unit_price": 450000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    new_price = 399000
    r = client.put(
        f"/api/price-lists/{pl['id']}/items/{item['id']}",
        json={"unit_price": new_price},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert float(r.json()["unit_price"]) == float(new_price)


def test_admin_can_remove_item_from_price_list(client, admin_token, db):
    item = _make_item(client, admin_token, code="PLI-DEL-001")
    pl = _make_price_list(client, admin_token, name="PL Remove")

    client.post(
        f"/api/price-lists/{pl['id']}/items",
        json={"item_id": item["id"], "unit_price": 450000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    r = client.delete(
        f"/api/price-lists/{pl['id']}/items/{item['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text

    # Confirm the item is gone from the price list detail
    r = client.get(
        f"/api/price-lists/{pl['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Price resolution (lookup)
# ─────────────────────────────────────────────────────────────────────────────

def test_lookup_returns_base_price_for_org_without_price_list(
        client, admin_token, db, client_org):
    item = _make_item(client, admin_token, code="LOOK-001", unit_price=500000)

    r = client.get(
        f"/api/items/lookup?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    prices = {i["id"]: i["unit_price"] for i in r.json()}
    assert prices[item["id"]] == 500000.0


def test_lookup_returns_overridden_price_for_org_with_price_list(
        client, admin_token, db, client_org):
    item = _make_item(client, admin_token, code="LOOK-OVR-001", unit_price=500000)
    pl = _make_price_list(client, admin_token, name="Override PL")

    # Add item at overridden price
    client.post(
        f"/api/price-lists/{pl['id']}/items",
        json={"item_id": item["id"], "unit_price": 450000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Assign price list to org
    r = client.put(
        f"/api/organizations/{client_org.id}/price-list",
        json={"price_list_id": pl["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"/api/items/lookup?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    prices = {i["id"]: i["unit_price"] for i in r.json()}
    assert prices[item["id"]] == 450000.0


def test_lookup_10_percent_discount(client, admin_token, db, client_org):
    base_price = 500000
    discounted_price = int(base_price * 0.9)  # 450000

    item = _make_item(client, admin_token, code="DISC10-001",
                      unit_price=base_price)
    pl = _make_price_list(client, admin_token, name="Premium PL 10pct")

    client.post(
        f"/api/price-lists/{pl['id']}/items",
        json={"item_id": item["id"], "unit_price": discounted_price},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    client.put(
        f"/api/organizations/{client_org.id}/price-list",
        json={"price_list_id": pl["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    r = client.get(
        f"/api/items/lookup?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    prices = {i["id"]: i["unit_price"] for i in r.json()}
    assert prices[item["id"]] == float(discounted_price)


def test_lookup_20_percent_discount(client, admin_token, db, client_org):
    base_price = 500000
    discounted_price = int(base_price * 0.8)  # 400000

    item = _make_item(client, admin_token, code="DISC20-001",
                      unit_price=base_price)
    pl = _make_price_list(client, admin_token, name="Premium PL 20pct")

    client.post(
        f"/api/price-lists/{pl['id']}/items",
        json={"item_id": item["id"], "unit_price": discounted_price},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    client.put(
        f"/api/organizations/{client_org.id}/price-list",
        json={"price_list_id": pl["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    r = client.get(
        f"/api/items/lookup?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    prices = {i["id"]: i["unit_price"] for i in r.json()}
    assert prices[item["id"]] == float(discounted_price)


def test_customer_cannot_lookup_other_org_prices(
        client, second_customer_token, db, client_org):
    r = client.get(
        f"/api/items/lookup?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {second_customer_token}"},
    )
    assert r.status_code == 403, r.text


def test_assign_price_list_to_org(client, admin_token, db, client_org):
    pl = _make_price_list(client, admin_token, name="Assigned PL")

    r = client.put(
        f"/api/organizations/{client_org.id}/price-list",
        json={"price_list_id": pl["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["price_list_id"] == pl["id"]
    assert data["price_list_name"] == pl["name"]
