from datetime import date, timedelta
from unittest.mock import patch

from tests.conftest import TestingSessionLocal


def _subscription(today: date, *, status="active", end_date=None, next_billing_date=None):
    from app.models.subscription import Subscription

    return Subscription(
        org_id=1,
        status=status,
        billing_cycle="monthly",
        start_date=today - timedelta(days=30),
        end_date=end_date,
        current_period_start=today - timedelta(days=30),
        current_period_end=today,
        next_billing_date=next_billing_date or today,
        due_days=15,
        tax_rate=0,
        unit_price=100,
    )


def test_effective_status_end_date_boundaries():
    from app.services.billing import effective_subscription_status

    today = date(2026, 7, 14)
    assert effective_subscription_status(
        _subscription(today, end_date=today - timedelta(days=1)), today
    ) == "expired"
    assert effective_subscription_status(_subscription(today, end_date=today), today) == "active"
    assert effective_subscription_status(
        _subscription(today, end_date=today + timedelta(days=1)), today
    ) == "active"


def test_effective_status_terminal_and_billing_precedence():
    from app.services.billing import effective_subscription_status

    today = date(2026, 7, 14)
    cancelled = _subscription(
        today,
        status="cancelled",
        end_date=today - timedelta(days=30),
        next_billing_date=today - timedelta(days=30),
    )
    assert effective_subscription_status(cancelled, today) == "cancelled"

    no_end_date = _subscription(
        today,
        end_date=None,
        next_billing_date=today - timedelta(days=3),
    )
    assert effective_subscription_status(no_end_date, today) == "past_due"


def test_subscription_checker_persists_linked_service_expiry(
    client, admin_token, client_org, db
):
    from app.models.item import Item
    from app.models.service import Service
    from app.models.subscription import Subscription
    from app.tasks.subscription_checker import check_subscriptions

    item = Item(
        code="EXPIRY-SYNC",
        name="Expiry sync service",
        type="hosting",
        unit_price=100_000,
        unit="month",
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    yesterday = date.today() - timedelta(days=1)
    response = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item.id,
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(yesterday),
            "billing_cycle": "monthly",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "active"
    subscription_id = response.json()["id"]

    detail = client.get(
        f"/api/subscriptions/{subscription_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "expired"

    with patch(
        "app.tasks.subscription_checker.SessionLocal",
        side_effect=TestingSessionLocal,
    ):
        result = check_subscriptions()

    db.commit()
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).one()
    service = db.query(Service).filter(Service.subscription_id == subscription_id).one()
    assert subscription.status == "expired"
    assert service.status == "inactive"
    assert service.expiry_date == yesterday
    assert result["expired"] >= 1

def test_list_filter_uses_effective_status(client, admin_token, client_org, db):
    expired = _subscription(
        date.today(),
        status="active",
        end_date=date.today() - timedelta(days=1),
        next_billing_date=date.today() + timedelta(days=30),
    )
    expired.org_id = client_org.id
    active = _subscription(
        date.today(),
        status="active",
        end_date=date.today() + timedelta(days=1),
        next_billing_date=date.today() + timedelta(days=30),
    )
    active.org_id = client_org.id
    db.add_all([expired, active])
    db.commit()
    db.refresh(expired)
    db.refresh(active)

    headers = {"Authorization": f"Bearer {admin_token}"}
    expired_response = client.get(
        "/api/subscriptions?status=expired&per_page=100",
        headers=headers,
    )
    active_response = client.get(
        "/api/subscriptions?status=active&per_page=100",
        headers=headers,
    )

    assert expired_response.status_code == 200
    assert active_response.status_code == 200
    expired_ids = {item["id"] for item in expired_response.json()["items"]}
    active_ids = {item["id"] for item in active_response.json()["items"]}
    assert expired.id in expired_ids
    assert expired.id not in active_ids
    assert active.id in active_ids


def test_checker_reconciles_service_for_already_expired_subscription(
    client, admin_token, client_org, db
):
    from app.models.item import Item
    from app.models.service import Service
    from app.models.subscription import Subscription
    from app.tasks.subscription_checker import check_subscriptions

    item = Item(
        code="STALE-EXPIRY-SYNC",
        name="Stale expiry sync service",
        type="hosting",
        unit_price=100_000,
        unit="month",
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    response = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item.id,
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(date.today() - timedelta(days=1)),
            "billing_cycle": "monthly",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    subscription_id = response.json()["id"]
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).one()
    service = db.query(Service).filter(Service.subscription_id == subscription_id).one()
    subscription.status = "expired"
    service.status = "active"
    db.commit()

    with patch(
        "app.tasks.subscription_checker.SessionLocal",
        side_effect=TestingSessionLocal,
    ):
        check_subscriptions()

    db.expire_all()
    service = db.query(Service).filter(Service.subscription_id == subscription_id).one()
    assert service.status == "inactive"



def test_future_start_subscription_is_scheduled_and_defers_invoice(client, admin_token, client_org, db):
    from app.models.item import Item
    from app.models.service import Service
    from app.models.invoice import Invoice

    item = Item(
        code="FUTURE-SCHEDULED",
        name="Future scheduled service",
        type="saas",
        unit_price=100_000,
        unit="month",
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    start_date = date.today() + timedelta(days=10)
    response = client.post(
        "/api/subscriptions",
        json={
            "org_id": client_org.id,
            "plan_id": item.id,
            "start_date": str(start_date),
            "billing_cycle": "monthly",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "active"

    detail = client.get(
        f"/api/subscriptions/{created['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "scheduled"

    scheduled_list = client.get(
        "/api/subscriptions?status=scheduled&per_page=100",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert scheduled_list.status_code == 200
    assert created["id"] in {item["id"] for item in scheduled_list.json()["items"]}

    service = db.query(Service).filter(Service.subscription_id == created["id"]).one()
    assert service.status == "inactive"
    assert db.query(Invoice).filter(Invoice.subscription_id == created["id"]).count() == 0
