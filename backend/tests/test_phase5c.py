# backend/tests/test_phase5c.py
"""
Phase 5C tests: Invoice feature — unit tests, service functions,
Celery task transitions, and API scope tests.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from tests.conftest import TestingSessionLocal


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_item_direct(db, code="ITEM-INV01"):
    from app.models.item import Item
    item = Item(code=code, name=f"Item {code}", type="saas",
                unit_price=Decimal("300000"), unit="month", is_active=True)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _make_plan_direct(db, item_id, code="PLAN-INV01", billing_cycle="monthly"):
    from app.models.subscription import SubscriptionPlan
    plan = SubscriptionPlan(code=code, name=f"Plan {code}", item_id=item_id,
                            billing_cycle=billing_cycle, trial_days=0, is_active=True)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _make_subscription_direct(db, org_id, plan_id, status="active", unit_price=300000):
    from app.models.subscription import Subscription
    today = date.today()
    sub = Subscription(
        org_id=org_id, subscription_plan_id=plan_id, status=status,
        start_date=today - timedelta(days=30),
        current_period_start=today - timedelta(days=30),
        current_period_end=today - timedelta(days=1),
        next_billing_date=today,
        unit_price=Decimal(str(unit_price)),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: generate_invoice_number (unit tests)
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_invoice_number_sequential(db):
    """Calling generate_invoice_number twice for the same year returns consecutive numbers."""
    from app.models.invoice import generate_invoice_number

    year = date.today().year
    first = generate_invoice_number(db, year)
    db.commit()
    second = generate_invoice_number(db, year)
    db.commit()

    assert first == f"INV-{year}-0001"
    assert second == f"INV-{year}-0002"


def test_generate_invoice_number_new_year_resets(db):
    """Calling generate_invoice_number for different years each starts at 0001."""
    from app.models.invoice import generate_invoice_number

    n2024 = generate_invoice_number(db, 2024)
    db.commit()
    n2025 = generate_invoice_number(db, 2025)
    db.commit()

    assert n2024 == "INV-2024-0001"
    assert n2025 == "INV-2025-0001"


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: create_invoice_from_subscription
# ─────────────────────────────────────────────────────────────────────────────

def test_create_invoice_from_subscription_totals(db, client_org):
    """Invoice totals: subtotal=300000, tax_amount=30000 (10%), total=330000."""
    from app.services.invoice_service import create_invoice_from_subscription

    item = _make_item_direct(db, "ITEM-INV-TOT01")
    plan = _make_plan_direct(db, item.id, code="PLAN-INV-TOT01")
    sub = _make_subscription_direct(db, client_org.id, plan.id, unit_price=300000)

    inv = create_invoice_from_subscription(sub.id, db)

    assert float(inv.subtotal) == 300000.0
    assert float(inv.tax_rate) == 10.0
    assert float(inv.tax_amount) == 30000.0
    assert float(inv.total) == 330000.0
    assert inv.status == "draft"


def test_create_invoice_from_subscription_description(db, client_org):
    """InvoiceLine description contains plan name and period dates."""
    from app.services.invoice_service import create_invoice_from_subscription
    from app.models.invoice import InvoiceLine

    item = _make_item_direct(db, "ITEM-INV-DESC01")
    plan = _make_plan_direct(db, item.id, code="PLAN-INV-DESC01")
    sub = _make_subscription_direct(db, client_org.id, plan.id)

    inv = create_invoice_from_subscription(sub.id, db)

    line = db.query(InvoiceLine).filter_by(invoice_id=inv.id).first()
    assert line is not None
    assert plan.name in line.description
    assert str(sub.current_period_start) in line.description
    assert str(sub.current_period_end) in line.description


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: send_invoice / mark_paid / cancel_invoice
# ─────────────────────────────────────────────────────────────────────────────

def test_send_invoice_changes_status(db, client_org):
    """Sending a draft invoice changes its status to 'sent'."""
    from app.services.invoice_service import create_manual_invoice, send_invoice

    inv = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Test line", "quantity": 1, "unit_price": 100000}],
        db=db,
    )
    assert inv.status == "draft"

    sent_inv = send_invoice(inv.id, db)
    assert sent_inv.status == "sent"


def test_send_invoice_notifies_customer(db, client_org, customer_user):
    """After sending an invoice, a Notification is created for the customer user."""
    from app.services.invoice_service import create_manual_invoice, send_invoice
    from app.models.notification import Notification

    inv = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Test line", "quantity": 1, "unit_price": 100000}],
        db=db,
    )
    send_invoice(inv.id, db)

    notif = db.query(Notification).filter_by(user_id=customer_user.id).first()
    assert notif is not None
    assert inv.invoice_number in notif.title


def test_send_invoice_non_draft_fails(client, db, client_org, admin_token):
    """Sending an already-sent invoice via the API returns HTTP 400."""
    from app.services.invoice_service import create_manual_invoice, send_invoice

    inv = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Test line", "quantity": 1, "unit_price": 100000}],
        db=db,
    )
    send_invoice(inv.id, db)

    r = client.put(
        f"/api/invoices/{inv.id}/send",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400


def test_mark_paid_sets_paid_at(db, client_org):
    """Marking a sent invoice as paid sets status='paid' and paid_at is not None."""
    from app.services.invoice_service import create_manual_invoice, send_invoice, mark_paid

    inv = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Test line", "quantity": 1, "unit_price": 100000}],
        db=db,
    )
    send_invoice(inv.id, db)
    paid_inv = mark_paid(inv.id, db)

    assert paid_inv.status == "paid"
    assert paid_inv.paid_at is not None


def test_cancel_invoice_draft(db, client_org):
    """Cancelling a draft invoice sets status='cancelled'."""
    from app.services.invoice_service import create_manual_invoice, cancel_invoice

    inv = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Test line", "quantity": 1, "unit_price": 100000}],
        db=db,
    )
    cancelled_inv = cancel_invoice(inv.id, db)
    assert cancelled_inv.status == "cancelled"


def test_cancel_paid_invoice_fails(client, db, client_org, admin_token):
    """Cancelling a paid invoice via the API returns HTTP 400."""
    from app.services.invoice_service import create_manual_invoice, send_invoice, mark_paid

    inv = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Test line", "quantity": 1, "unit_price": 100000}],
        db=db,
    )
    send_invoice(inv.id, db)
    mark_paid(inv.id, db)

    r = client.put(
        f"/api/invoices/{inv.id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: check_overdue_invoices task
# ─────────────────────────────────────────────────────────────────────────────

def test_check_overdue_marks_sent_past_due(db, client_org, admin_user):
    """A sent invoice with due_date in the past is marked overdue by the task."""
    from app.models.invoice import Invoice, generate_invoice_number
    from app.tasks.invoice_tasks import check_overdue_invoices
    from unittest.mock import patch

    today = date.today()
    inv_number = generate_invoice_number(db, today.year)
    db.commit()

    inv = Invoice(
        invoice_number=inv_number,
        org_id=client_org.id,
        status="sent",
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=1),
        subtotal=Decimal("100000"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("10000"),
        total=Decimal("110000"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    inv_id = inv.id

    with patch("app.tasks.invoice_tasks.SessionLocal", side_effect=TestingSessionLocal):
        result = check_overdue_invoices()

    db.commit()
    refreshed = db.query(Invoice).filter_by(id=inv_id).first()
    assert refreshed.status == "overdue"
    assert result["overdue"] >= 1


def test_check_overdue_does_not_touch_paid(db, client_org, admin_user):
    """A paid invoice with past due_date stays 'paid' after the task runs."""
    from app.models.invoice import Invoice, generate_invoice_number
    from app.tasks.invoice_tasks import check_overdue_invoices
    from unittest.mock import patch

    today = date.today()
    inv_number = generate_invoice_number(db, today.year)
    db.commit()

    inv = Invoice(
        invoice_number=inv_number,
        org_id=client_org.id,
        status="paid",
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=1),
        subtotal=Decimal("100000"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("10000"),
        total=Decimal("110000"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    inv_id = inv.id

    with patch("app.tasks.invoice_tasks.SessionLocal", side_effect=TestingSessionLocal):
        check_overdue_invoices()

    db.commit()
    refreshed = db.query(Invoice).filter_by(id=inv_id).first()
    assert refreshed.status == "paid"


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: auto_generate_invoices task
# ─────────────────────────────────────────────────────────────────────────────

def test_auto_generate_creates_invoice(db, client_org):
    """Active subscription with next_billing_date=today triggers invoice creation."""
    from app.models.invoice import Invoice
    from app.tasks.invoice_tasks import auto_generate_invoices
    from unittest.mock import patch

    item = _make_item_direct(db, "ITEM-INV-AUTO01")
    plan = _make_plan_direct(db, item.id, code="PLAN-INV-AUTO01")
    _make_subscription_direct(db, client_org.id, plan.id, status="active")

    with patch("app.tasks.invoice_tasks.SessionLocal", side_effect=TestingSessionLocal):
        result = auto_generate_invoices()

    db.commit()
    count = db.query(Invoice).filter_by(org_id=client_org.id).count()
    assert count >= 1
    assert result["generated"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Section 6: API scope
# ─────────────────────────────────────────────────────────────────────────────

def test_customer_cannot_see_other_org_invoice(
    client, client_org, second_customer_token, second_client_org, admin_token, db
):
    """Customer from second_client_org cannot GET an invoice belonging to client_org."""
    from app.services.invoice_service import create_manual_invoice

    inv = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Line 1", "quantity": 1, "unit_price": 50000}],
        db=db,
    )

    r = client.get(
        f"/api/invoices/{inv.id}",
        headers={"Authorization": f"Bearer {second_customer_token}"},
    )
    assert r.status_code == 403, r.text


def test_customer_cannot_post_invoice(client, customer_token, client_org):
    """Customer cannot create an invoice via POST /api/invoices."""
    r = client.post(
        "/api/invoices",
        json={
            "org_id": client_org.id,
            "lines": [{"description": "Line 1", "quantity": 1, "unit_price": 50000}],
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 403, r.text


def test_customer_my_invoices_scoped(
    client, db, client_org, second_client_org,
    customer_token, second_customer_token,
):
    """GET /api/invoices/my returns only the invoices for the customer's own org."""
    from app.services.invoice_service import create_manual_invoice

    # One invoice for client_org (customer_token's org)
    create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Line A", "quantity": 1, "unit_price": 50000}],
        db=db,
    )
    # One invoice for second_client_org
    create_manual_invoice(
        org_id=second_client_org.id,
        lines_data=[{"description": "Line B", "quantity": 1, "unit_price": 50000}],
        db=db,
    )

    r = client.get(
        "/api/invoices/my",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    assert data[0]["org_id"] == client_org.id


def test_admin_sees_all_invoices(
    client, db, client_org, second_client_org, admin_token
):
    """Admin GET /api/invoices sees invoices from all orgs."""
    from app.services.invoice_service import create_manual_invoice

    create_manual_invoice(
        org_id=client_org.id,
        lines_data=[{"description": "Line A", "quantity": 1, "unit_price": 50000}],
        db=db,
    )
    create_manual_invoice(
        org_id=second_client_org.id,
        lines_data=[{"description": "Line B", "quantity": 1, "unit_price": 50000}],
        db=db,
    )

    r = client.get(
        "/api/invoices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 2


def test_non_customer_denied_my_endpoint(client, admin_token):
    """Admin token gets 403 from GET /api/invoices/my."""
    r = client.get(
        "/api/invoices/my",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 403, r.text
