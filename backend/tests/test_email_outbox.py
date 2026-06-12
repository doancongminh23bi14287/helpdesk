# backend/tests/test_email_outbox.py
"""
Tests for the email outbox pattern in invoice delivery.

Core invariant: invoice.status and outbox creation are committed atomically.
SMTP failures after that commit only affect outbox retry state — the invoice
remains 'sent' regardless of delivery outcome.

Tests call drain_outbox(db) directly (the same pattern as test_email_piping.py
calling process_inbox(db)) so both test and service share one DB session,
avoiding MySQL REPEATABLE READ isolation issues with separate connections.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch


PATCH_SEND = "app.services.outbox_service.send_email"


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_invoice(db, org_id: int) -> "Invoice":
    """Create a minimal draft invoice with one line item."""
    from app.models.invoice import Invoice, InvoiceLine, generate_invoice_number
    from datetime import date

    number = generate_invoice_number(db, date.today().year)
    invoice = Invoice(
        invoice_number=number,
        org_id=org_id,
        status="draft",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        subtotal=Decimal("1000000"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("100000"),
        total=Decimal("1100000"),
    )
    db.add(invoice)
    db.flush()

    line = InvoiceLine(
        invoice_id=invoice.id,
        description="Service fee",
        quantity=Decimal("1"),
        unit_price=Decimal("1000000"),
        line_total=Decimal("1000000"),
    )
    db.add(line)
    db.commit()
    db.refresh(invoice)
    return invoice


def _make_outbox(db, status="pending", retry_count=0, max_retries=3) -> "EmailOutbox":
    from app.models.email_outbox import EmailOutbox
    outbox = EmailOutbox(
        email_type="invoice",
        recipient_email="customer@test.com",
        subject="Test invoice",
        body_html="<p>Invoice</p>",
        body_text="Invoice",
        status=status,
        retry_count=retry_count,
        max_retries=max_retries,
        related_type="invoice",
        related_id=1,
        scheduled_at=datetime.utcnow() - timedelta(seconds=1),  # past due
    )
    db.add(outbox)
    db.commit()
    db.refresh(outbox)
    return outbox


# ── tests ─────────────────────────────────────────────────────────────────────

def test_send_invoice_creates_outbox_record(db, client_org, customer_user):
    """
    send_invoice() atomically marks invoice as 'sent' and writes an outbox
    record per recipient without touching SMTP at all.
    """
    from app.services.invoice_service import send_invoice
    from app.models.email_outbox import EmailOutbox

    invoice = _make_invoice(db, client_org.id)

    # No SMTP mock needed — the new flow never calls send_email() directly
    result = send_invoice(invoice.id, db)

    assert result.status == "sent"
    assert result.sent_at is not None

    outboxes = db.query(EmailOutbox).filter(
        EmailOutbox.related_id == invoice.id,
        EmailOutbox.related_type == "invoice",
    ).all()
    assert len(outboxes) >= 1
    for o in outboxes:
        assert o.status == "pending"
        assert o.email_type == "invoice"
        assert o.recipient_email == customer_user.email
        assert o.body_html is not None


def test_outbox_task_sends_pending_email(db):
    """
    drain_outbox() delivers a pending record and marks it 'sent'.
    """
    from app.services.outbox_service import drain_outbox
    from app.models.email_outbox import EmailOutbox

    outbox = _make_outbox(db)

    with patch(PATCH_SEND, return_value="<abc123@osd.vn>"):
        result = drain_outbox(db)

    db.refresh(outbox)
    assert outbox.status == "sent"
    assert outbox.sent_at is not None
    assert outbox.retry_count == 0
    assert result["sent"] == 1
    assert result["failed"] == 0


def test_admin_can_list_email_outbox(client, admin_token, db):
    outbox = _make_outbox(db, status="failed", retry_count=3)

    r = client.get(
        "/api/admin/email-outbox?status=failed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == outbox.id
    assert body["items"][0]["status"] == "failed"


def test_admin_can_retry_failed_email_outbox(client, admin_token, db):
    outbox = _make_outbox(db, status="failed", retry_count=3)
    outbox.last_error = "smtp failed"
    outbox.failed_at = datetime.utcnow()
    db.commit()

    r = client.post(
        f"/api/admin/email-outbox/{outbox.id}/retry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["last_error"] is None
    db.refresh(outbox)
    assert outbox.status == "pending"


def test_outbox_task_retries_on_smtp_failure(db):
    """
    When send_email() fails (returns None), the record is rescheduled
    with incremented retry_count and a future scheduled_at.
    """
    from app.services.outbox_service import drain_outbox

    outbox = _make_outbox(db)
    before = datetime.utcnow()

    with patch(PATCH_SEND, return_value=None):
        result = drain_outbox(db)

    db.refresh(outbox)
    assert outbox.status == "pending"
    assert outbox.retry_count == 1
    assert outbox.last_error is not None
    assert outbox.scheduled_at > before
    assert result["sent"] == 0
    assert result["failed"] == 0   # not yet at max_retries


def test_outbox_task_marks_failed_after_max_retries(db):
    """
    Once retry_count reaches max_retries the record is marked 'failed'
    and failed_at is set. No further retries are attempted.
    """
    from app.services.outbox_service import drain_outbox

    outbox = _make_outbox(db, retry_count=2, max_retries=3)

    with patch(PATCH_SEND, return_value=None):
        result = drain_outbox(db)

    db.refresh(outbox)
    assert outbox.status == "failed"
    assert outbox.retry_count == 3
    assert outbox.failed_at is not None
    assert result["failed"] == 1


def test_invoice_status_set_even_if_smtp_later_fails(db, client_org, customer_user):
    """
    invoice.status is 'sent' the moment send_invoice() commits, regardless
    of whether subsequent outbox delivery attempts succeed or fail.
    The outbox tracks delivery failure; the invoice is never rolled back.
    """
    from app.services.invoice_service import send_invoice
    from app.services.outbox_service import drain_outbox
    from app.models.invoice import Invoice
    from app.models.email_outbox import EmailOutbox

    invoice = _make_invoice(db, client_org.id)
    send_invoice(invoice.id, db)

    db.refresh(invoice)
    assert invoice.status == "sent"

    # Run the drain task three times with SMTP always failing
    with patch(PATCH_SEND, return_value=None):
        drain_outbox(db)   # retry_count 0→1, pending (rescheduled)

    # Force scheduled_at back to the past so subsequent runs pick it up
    outboxes = db.query(EmailOutbox).filter(
        EmailOutbox.related_id == invoice.id,
        EmailOutbox.related_type == "invoice",
    ).all()
    for o in outboxes:
        o.scheduled_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    with patch(PATCH_SEND, return_value=None):
        drain_outbox(db)   # retry_count 1→2, pending (rescheduled)

    for o in outboxes:
        db.refresh(o)
        o.scheduled_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    with patch(PATCH_SEND, return_value=None):
        drain_outbox(db)   # retry_count 2→3 = max_retries → failed

    # Invoice state is untouched by delivery failures
    db.refresh(invoice)
    assert invoice.status == "sent"

    for o in outboxes:
        db.refresh(o)
    assert all(o.status == "failed" for o in outboxes)
    assert all(o.retry_count == 3 for o in outboxes)


def test_outbox_task_skips_exhausted_records(db):
    """
    Records at max_retries (status='failed') are not picked up by drain_outbox.
    """
    from app.services.outbox_service import drain_outbox

    outbox = _make_outbox(db, status="failed", retry_count=3, max_retries=3)

    with patch(PATCH_SEND, return_value="<mid@osd.vn>") as mock_send:
        result = drain_outbox(db)

    mock_send.assert_not_called()
    db.refresh(outbox)
    assert outbox.status == "failed"
    assert result["processed"] == 0


def test_outbox_task_respects_scheduled_at(db):
    """
    Records with scheduled_at in the future are not delivered until their
    scheduled time arrives.
    """
    from app.services.outbox_service import drain_outbox

    outbox = _make_outbox(db, status="pending")
    outbox.scheduled_at = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    with patch(PATCH_SEND, return_value="<mid@osd.vn>") as mock_send:
        result = drain_outbox(db)

    mock_send.assert_not_called()
    db.refresh(outbox)
    assert outbox.status == "pending"
    assert result["processed"] == 0
