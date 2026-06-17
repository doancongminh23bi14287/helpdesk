"""Tests for: service optional on ticket create + item catalogue requested_item_id."""
import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def hosting_item(db):
    from app.models.item import Item
    item = Item(
        code="HOST-TEST-S",
        name="LS-S (VN) Test",
        type="hosting",
        unit_price=70_000,
        unit="month",
        description="HDD: 1.200 Mb | Lưu lượng: 36.000 Mb/tháng",
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def inactive_item(db):
    from app.models.item import Item
    item = Item(
        code="HOST-TEST-DEAD",
        name="Dead Plan",
        type="hosting",
        unit_price=1_000,
        unit="month",
        description="Disabled plan",
        is_active=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ── 1. No service → 201 ───────────────────────────────────────────────────────

def test_create_ticket_without_service_returns_201(
    client, customer_token, client_org
):
    """Customer can submit a ticket without selecting a service."""
    r = client.post(
        "/api/tickets",
        json={
            "org_id": client_org.id,
            "subject": "General question",
            "ticket_type": "Question",
            "description": "I have a question.",
        },
        headers=auth(customer_token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["service_id"] is None
    assert data["status"] == "Open"


# ── 2. requested_item_id → description appended ───────────────────────────────

def test_change_request_with_requested_item_appends_note(
    client, customer_token, client_org, hosting_item
):
    """Change Request with requested_item_id should append item name+code to description."""
    r = client.post(
        "/api/tickets",
        json={
            "org_id": client_org.id,
            "subject": "Muốn nâng cấp gói hosting",
            "ticket_type": "Change Request",
            "description": "Tôi muốn đổi gói.",
            "requested_item_id": hosting_item.id,
        },
        headers=auth(customer_token),
    )
    assert r.status_code == 201, r.text
    desc = r.json()["description"]
    assert hosting_item.name in desc
    assert hosting_item.code in desc
    assert "[Gói khách quan tâm:" in desc


# ── 3. Service from wrong org → 422 ──────────────────────────────────────────

def test_create_ticket_service_wrong_org_rejected(
    client, customer_token, client_org, second_client_org, db
):
    """Service belonging to a different org must be rejected."""
    from app.models.service import Service
    other_svc = Service(org_id=second_client_org.id, name="Other Hosting", type="hosting", status="active")
    db.add(other_svc)
    db.commit()
    db.refresh(other_svc)

    r = client.post(
        "/api/tickets",
        json={
            "org_id": client_org.id,
            "service_id": other_svc.id,
            "subject": "Wrong service",
            "description": "Trying wrong service.",
        },
        headers=auth(customer_token),
    )
    assert r.status_code in (400, 422), r.text


# ── 4. Customer GET /api/items → 200 with only active items ──────────────────

def test_customer_can_list_active_items(
    client, customer_token, hosting_item, inactive_item
):
    """GET /api/items is accessible to customers and returns only active items."""
    r = client.get("/api/items", headers=auth(customer_token))
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    ids = {i["id"] for i in items}
    assert hosting_item.id in ids
    assert inactive_item.id not in ids
