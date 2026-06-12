# backend/tests/test_phase5b.py
"""
Phase 5B tests: Billing Logic, Subscription Plan API,
Subscription CRUD + Scope, Price Resolution, and Celery Task Transitions.
"""

import pytest
from datetime import date
from tests.conftest import TestingSessionLocal

# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Billing Logic (pure unit tests — no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

from app.services.billing import compute_period_end, compute_next_billing_date


def test_period_end_monthly_normal():
    assert compute_period_end(date(2024, 1, 1), "monthly") == date(2024, 2, 1)


def test_period_end_monthly_month_end():
    # Jan 31 + 1 month = Feb 29 in leap year 2024
    assert compute_period_end(date(2024, 1, 31), "monthly") == date(2024, 2, 29)


def test_period_end_monthly_non_leap():
    # Jan 31 + 1 month = Feb 28 in non-leap year 2023
    assert compute_period_end(date(2023, 1, 31), "monthly") == date(2023, 2, 28)


def test_period_end_monthly_apr_30():
    # Mar 31 + 1 month = Apr 30
    assert compute_period_end(date(2024, 3, 31), "monthly") == date(2024, 4, 30)


def test_period_end_quarterly():
    assert compute_period_end(date(2024, 1, 1), "quarterly") == date(2024, 4, 1)


def test_period_end_yearly():
    assert compute_period_end(date(2024, 1, 1), "yearly") == date(2025, 1, 1)


def test_period_end_invalid_cycle():
    with pytest.raises(ValueError):
        compute_period_end(date(2024, 1, 1), "weekly")


def test_next_billing_date():
    assert compute_next_billing_date(date(2024, 1, 31)) == date(2024, 2, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_item(client, admin_token, code="SVC-T01"):
    r = client.post(
        "/api/items",
        json={"code": code, "name": f"Item {code}", "type": "saas",
              "unit_price": 500000, "unit": "month"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _make_plan(client, admin_token, item_id, code="PLAN-T01"):
    r = client.post(
        "/api/subscription-plans",
        json={"code": code, "name": f"Plan {code}", "item_id": item_id,
              "billing_cycle": "monthly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Subscription Plan API
# ─────────────────────────────────────────────────────────────────────────────

def test_admin_can_create_subscription_plan(client, admin_token):
    item = _make_item(client, admin_token)
    plan = _make_plan(client, admin_token, item["id"])
    assert plan["code"] == "PLAN-T01"
    assert plan["billing_cycle"] == "monthly"
    assert plan["is_active"] is True


def test_list_plans_returns_created_plan(client, admin_token):
    item = _make_item(client, admin_token)
    _make_plan(client, admin_token, item["id"])
    r = client.get(
        "/api/subscription-plans",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    codes = [p["code"] for p in r.json()]
    assert "PLAN-T01" in codes


def test_duplicate_plan_code_rejected(client, admin_token):
    item = _make_item(client, admin_token, code="SVC-DUP01")
    _make_plan(client, admin_token, item["id"], "PLAN-DUP")
    r = client.post(
        "/api/subscription-plans",
        json={"code": "PLAN-DUP", "name": "Dup", "item_id": item["id"],
              "billing_cycle": "monthly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code in (400, 409)


def test_update_plan_deactivate(client, admin_token):
    item = _make_item(client, admin_token, code="SVC-DEACT01")
    plan = _make_plan(client, admin_token, item["id"], code="PLAN-DEACT01")
    r = client.put(
        f"/api/subscription-plans/{plan['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Subscription CRUD + Scope
# ─────────────────────────────────────────────────────────────────────────────

def test_create_subscription(client, admin_token, db, client_org):
    item = _make_item(client, admin_token, "SVC-SUB01")
    r = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": item["id"],
              "start_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "active"
    assert data["org_id"] == client_org.id
    assert data["item_id"] == item["id"]
    assert data["subscription_plan_id"] is None
    assert data["current_period_end"] == "2024-02-01"


def test_subscription_create_stores_due_days_and_tax_rate(client, admin_token, db, client_org):
    item = _make_item(client, admin_token, "SVC-DUE-TAX01")

    r = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item["id"],
            "start_date": "2024-06-01",
            "due_days": 21,
            "tax_rate": 7.5,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "active"
    assert data["trial_end_date"] is None
    assert data["due_days"] == 21
    assert float(data["tax_rate"]) == 7.5


def test_cancel_subscription(client, admin_token, db, client_org):
    item = _make_item(client, admin_token, "SVC-CANCEL01")
    sub = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": item["id"],
              "start_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    r = client.put(
        f"/api/subscriptions/{sub['id']}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert r.json()["cancelled_at"] is not None


def test_cancel_already_cancelled_fails(client, admin_token, db, client_org):
    item = _make_item(client, admin_token, "SVC-CANCEL02")
    sub = client.post(
        "/api/subscriptions",
        json={"org_id": client_org.id, "plan_id": item["id"],
              "start_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    client.put(
        f"/api/subscriptions/{sub['id']}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Try cancelling again
    r = client.put(
        f"/api/subscriptions/{sub['id']}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400


def test_customer_sees_only_own_subscriptions(client, db, client_org, provider_org):
    from app.models.user import User
    from app.core.security import hash_password

    # Create a customer user for client_org
    customer = User(
        org_id=client_org.id,
        email="cust@test.com",
        password_hash=hash_password("pass"),
        full_name="Cust",
        role="customer",
        is_active=True,
    )
    db.add(customer)
    db.commit()

    r = client.post("/api/auth/login", json={"email": "cust@test.com", "password": "pass"})
    token = r.json()["access_token"]

    r = client.get(
        "/api/subscriptions/my",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    # Should only return subscriptions for their org
    data = r.json()
    assert all(s["org_id"] == client_org.id for s in data)


def test_non_customer_denied_my_endpoint(client, admin_token):
    r = client.get(
        "/api/subscriptions/my",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: Price Resolution
# ─────────────────────────────────────────────────────────────────────────────

def test_subscription_uses_item_price_and_cycle_discount(client, admin_token, db, client_org):
    item = _make_item(client, admin_token, "SVC-PRICE01")
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
    assert r.status_code == 201
    assert float(r.json()["unit_price"]) == 1425000.0


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Celery Task Transitions (unit tests using direct DB manipulation)
# ─────────────────────────────────────────────────────────────────────────────

def _make_subscription_direct(db, org_id, plan_id, status, start_date,
                               current_period_end, next_billing_date,
                               trial_end_date=None, unit_price=500000):
    """Helper to create a subscription directly in DB for task transition tests."""
    from app.models.subscription import Subscription
    from decimal import Decimal

    sub = Subscription(
        org_id=org_id,
        subscription_plan_id=plan_id,
        status=status,
        start_date=start_date,
        trial_end_date=trial_end_date,
        current_period_start=start_date,
        current_period_end=current_period_end,
        next_billing_date=next_billing_date,
        unit_price=Decimal(str(unit_price)),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _make_plan_direct(db, item_id, code="PLAN-TASK01", billing_cycle="monthly"):
    """Helper to create a subscription plan directly in DB."""
    from app.models.subscription import SubscriptionPlan

    plan = SubscriptionPlan(
        code=code,
        name=f"Plan {code}",
        item_id=item_id,
        billing_cycle=billing_cycle,
        trial_days=0,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _make_item_direct(db, code="ITEM-TASK01"):
    """Helper to create an item directly in DB."""
    from app.models.item import Item
    from decimal import Decimal

    item = Item(
        code=code,
        name=f"Item {code}",
        type="saas",
        unit_price=Decimal("500000"),
        unit="month",
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_task_trial_transitions_to_active(db, client_org):
    """Trial subscription with expired trial_end_date transitions to active."""
    from app.tasks.subscription_checker import check_subscriptions
    from app.models.subscription import Subscription
    from datetime import timedelta
    from unittest.mock import patch

    today = date.today()
    item = _make_item_direct(db, "ITEM-TASK-TRIAL01")
    plan = _make_plan_direct(db, item.id, code="PLAN-TASK-TRIAL01")

    sub = _make_subscription_direct(
        db,
        org_id=client_org.id,
        plan_id=plan.id,
        status="trial",
        start_date=today - timedelta(days=20),
        current_period_end=today + timedelta(days=10),
        next_billing_date=today + timedelta(days=11),
        trial_end_date=today - timedelta(days=1),  # trial already ended
    )

    # Patch SessionLocal so the task uses our test DB session
    from app.database import SessionLocal
    with patch("app.tasks.subscription_checker.SessionLocal", side_effect=TestingSessionLocal):
        result = check_subscriptions()

    # Commit test session to start fresh transaction (MySQL REPEATABLE READ)
    db.commit()
    refreshed = db.query(Subscription).filter_by(id=sub.id).first()
    assert refreshed.status == "active"
    assert result["trial_to_active"] >= 1


def test_task_active_transitions_to_past_due(db, client_org):
    """Active subscription overdue (not yet grace exhausted) transitions to past_due."""
    from app.tasks.subscription_checker import check_subscriptions
    from app.models.subscription import Subscription
    from datetime import timedelta
    from unittest.mock import patch

    today = date.today()
    item = _make_item_direct(db, "ITEM-TASK-DUE01")
    plan = _make_plan_direct(db, item.id, code="PLAN-TASK-DUE01")

    sub = _make_subscription_direct(
        db,
        org_id=client_org.id,
        plan_id=plan.id,
        status="active",
        start_date=today - timedelta(days=40),
        current_period_end=today - timedelta(days=10),
        next_billing_date=today - timedelta(days=3),  # overdue, within grace period (< 7 days)
    )

    with patch("app.tasks.subscription_checker.SessionLocal", side_effect=TestingSessionLocal):
        result = check_subscriptions()

    db.commit()
    refreshed = db.query(Subscription).filter_by(id=sub.id).first()
    assert refreshed.status == "past_due"
    assert result["past_due"] >= 1


def test_task_active_transitions_to_expired(db, client_org):
    """Active subscription past grace period (> 7 days overdue) transitions to expired."""
    from app.tasks.subscription_checker import check_subscriptions
    from app.models.subscription import Subscription
    from datetime import timedelta
    from unittest.mock import patch

    today = date.today()
    item = _make_item_direct(db, "ITEM-TASK-EXP01")
    plan = _make_plan_direct(db, item.id, code="PLAN-TASK-EXP01")

    sub = _make_subscription_direct(
        db,
        org_id=client_org.id,
        plan_id=plan.id,
        status="active",
        start_date=today - timedelta(days=60),
        current_period_end=today - timedelta(days=20),
        next_billing_date=today - timedelta(days=10),  # more than 7 days overdue
    )

    with patch("app.tasks.subscription_checker.SessionLocal", side_effect=TestingSessionLocal):
        result = check_subscriptions()

    db.commit()
    refreshed = db.query(Subscription).filter_by(id=sub.id).first()
    assert refreshed.status == "expired"
    assert result["expired"] >= 1


def test_task_cancelled_subscription_not_changed(db, client_org):
    """Cancelled subscriptions are not touched by the task."""
    from app.tasks.subscription_checker import check_subscriptions
    from app.models.subscription import Subscription
    from datetime import timedelta
    from unittest.mock import patch

    today = date.today()
    item = _make_item_direct(db, "ITEM-TASK-CANC01")
    plan = _make_plan_direct(db, item.id, code="PLAN-TASK-CANC01")

    sub = _make_subscription_direct(
        db,
        org_id=client_org.id,
        plan_id=plan.id,
        status="cancelled",
        start_date=today - timedelta(days=60),
        current_period_end=today - timedelta(days=30),
        next_billing_date=today - timedelta(days=15),  # would normally expire
    )

    with patch("app.tasks.subscription_checker.SessionLocal", side_effect=TestingSessionLocal):
        check_subscriptions()

    db.commit()
    refreshed = db.query(Subscription).filter_by(id=sub.id).first()
    # Status must remain cancelled
    assert refreshed.status == "cancelled"
