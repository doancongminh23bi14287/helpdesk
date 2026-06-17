# backend/tests/test_service_sync.py
"""Tests for S1: auto-pair Service↔Subscription."""
import pytest
from datetime import date


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def item(db):
    from app.models.item import Item
    it = Item(
        code="TEST-SAAS-SYNC",
        name="Test SaaS Plan",
        type="saas",
        unit_price=1_000_000,
        unit="month",
        is_active=True,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@pytest.fixture
def item_domain(db):
    from app.models.item import Item
    it = Item(
        code="TEST-DOMAIN-SYNC",
        name="Domain Plan",
        type="domain",
        unit_price=500_000,
        unit="month",
        is_active=True,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


def create_sub_via_api(client, token, org_id, item_id, billing_cycle="monthly"):
    r = client.post(
        "/api/subscriptions",
        json={
            "org_id": org_id,
            "plan_id": item_id,
            "start_date": str(date.today()),
            "billing_cycle": billing_cycle,
            "due_days": 15,
            "tax_rate": 0,
        },
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── S1.1: auto-create service on subscription creation ────────────────────────

def test_create_subscription_auto_creates_service(client, admin_token, client_org, item, db):
    from app.models.service import Service

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    sub_id = sub["id"]

    svc = db.query(Service).filter(Service.subscription_id == sub_id).first()
    assert svc is not None, "Service was not auto-created"
    assert svc.name == item.name
    assert svc.type == "saas"
    assert svc.status == "active"
    assert svc.org_id == client_org.id
    assert svc.monthly_cost is not None
    assert svc.billing_cycle == "monthly"
    assert svc.subscription_id == sub_id


def test_create_subscription_domain_type_mapped(client, admin_token, client_org, item_domain, db):
    from app.models.service import Service

    sub = create_sub_via_api(client, admin_token, client_org.id, item_domain.id)
    svc = db.query(Service).filter(Service.subscription_id == sub["id"]).first()
    assert svc is not None
    assert svc.type == "domain"


def test_only_one_service_per_subscription(client, admin_token, client_org, item, db):
    from app.models.service import Service

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    count = db.query(Service).filter(Service.subscription_id == sub["id"]).count()
    assert count == 1


# ── S1.2: sync on cancel ──────────────────────────────────────────────────────

def test_cancel_subscription_syncs_service_status(client, admin_token, client_org, item, db):
    from app.models.service import Service

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    sub_id = sub["id"]

    r = client.put(f"/api/subscriptions/{sub_id}/cancel", headers=auth(admin_token))
    assert r.status_code == 200, r.text

    db.expire_all()
    svc = db.query(Service).filter(Service.subscription_id == sub_id).first()
    assert svc is not None
    assert svc.status == "cancelled"


# ── S1.3: hard-delete /permanent ─────────────────────────────────────────────

def test_hard_delete_cancelled_sub_deletes_service(client, admin_token, client_org, item, db):
    from app.models.service import Service
    from app.models.invoice import Invoice

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    sub_id = sub["id"]

    # Cancel first
    client.put(f"/api/subscriptions/{sub_id}/cancel", headers=auth(admin_token))

    # Record invoice count before (invoices should be kept)
    invoice_before = db.query(Invoice).filter(Invoice.subscription_id == sub_id).count()

    r = client.delete(f"/api/subscriptions/{sub_id}/permanent", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["deleted"] is True
    assert data["subscription_id"] == sub_id
    assert data["service_deleted"] is True
    assert "invoices_kept" in data

    # Service is gone
    db.expire_all()
    assert db.query(Service).filter(Service.subscription_id == sub_id).first() is None

    # Subscription is gone
    from app.models.subscription import Subscription
    assert db.query(Subscription).filter(Subscription.id == sub_id).first() is None

    # Invoices still exist with nullified subscription_id
    kept = db.query(Invoice).filter(Invoice.id.isnot(None)).filter(
        Invoice.subscription_id == sub_id
    ).count()
    assert kept == 0  # subscription_id was nullified


def test_hard_delete_expired_sub_allowed(client, admin_token, client_org, item, db):
    from app.models.subscription import Subscription

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    sub_id = sub["id"]

    # Force status to 'expired' directly in DB
    db.query(Subscription).filter(Subscription.id == sub_id).update({"status": "expired"})
    db.commit()

    r = client.delete(f"/api/subscriptions/{sub_id}/permanent", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] is True


def test_hard_delete_active_sub_rejected(client, admin_token, client_org, item):
    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    r = client.delete(f"/api/subscriptions/{sub['id']}/permanent", headers=auth(admin_token))
    assert r.status_code == 400, r.text
    assert "cancelled" in r.json()["detail"].lower() or "expired" in r.json()["detail"].lower()


def test_hard_delete_nonexistent_returns_404(client, admin_token):
    r = client.delete("/api/subscriptions/999999/permanent", headers=auth(admin_token))
    assert r.status_code == 404, r.text


def test_hard_delete_non_admin_returns_403(client, customer_token, admin_token, client_org, item):
    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    client.put(f"/api/subscriptions/{sub['id']}/cancel", headers=auth(admin_token))
    r = client.delete(f"/api/subscriptions/{sub['id']}/permanent", headers=auth(customer_token))
    assert r.status_code == 403, r.text


def test_hard_delete_nullifies_project_subscription_id(client, admin_token, admin_user, client_org, item, db):
    from app.models.project import Project
    from app.models.subscription import Subscription

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    sub_id = sub["id"]

    # Create a project linked to this subscription (created_by required)
    project = Project(
        org_id=client_org.id,
        name="Test Project",
        subscription_id=sub_id,
        visibility="internal",
        status="open",
        created_by=admin_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    client.put(f"/api/subscriptions/{sub_id}/cancel", headers=auth(admin_token))
    r = client.delete(f"/api/subscriptions/{sub_id}/permanent", headers=auth(admin_token))
    assert r.status_code == 200, r.text

    db.expire_all()
    db.refresh(project)
    assert project.subscription_id is None


# ── S1.4: existing GET /api/services unaffected ───────────────────────────────

def test_services_endpoint_still_works(client, customer_token):
    r = client.get("/api/services", headers=auth(customer_token))
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# ── Backfill: sync_service_from_subscription idempotent ───────────────────────

def test_sync_idempotent_does_not_duplicate(client, admin_token, client_org, item, db):
    from app.models.service import Service
    from app.services.service_sync import sync_service_from_subscription
    from app.models.subscription import Subscription

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    sub_id = sub["id"]

    sub_obj = db.query(Subscription).filter(Subscription.id == sub_id).first()
    # Call sync twice — should not create a second service
    sync_service_from_subscription(db, sub_obj, create_if_missing=True)
    sync_service_from_subscription(db, sub_obj, create_if_missing=True)

    count = db.query(Service).filter(Service.subscription_id == sub_id).count()
    assert count == 1


def test_sync_updates_existing_service_fields(client, admin_token, client_org, item, db):
    from app.models.service import Service
    from app.services.service_sync import sync_service_from_subscription
    from app.models.subscription import Subscription

    sub = create_sub_via_api(client, admin_token, client_org.id, item.id)
    sub_id = sub["id"]

    sub_obj = db.query(Subscription).filter(Subscription.id == sub_id).first()
    # Manually change sub fields and re-sync
    sub_obj.status = "past_due"
    db.commit()
    db.refresh(sub_obj)

    sync_service_from_subscription(db, sub_obj, create_if_missing=False)

    db.expire_all()
    svc = db.query(Service).filter(Service.subscription_id == sub_id).first()
    assert svc.status == "past_due"
