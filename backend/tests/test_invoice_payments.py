# backend/tests/test_invoice_payments.py
"""
Tests for the invoice_payments table and associated API endpoints.

Covers:
  - POST /api/invoices/{id}/payments  (record_payment)
  - GET  /api/invoices/{id}/payments  (list_payments)
  - PUT  /api/invoices/{id}/mark-paid (legacy endpoint — must create payment row)
  - Role enforcement (customers get 403)
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_sent_invoice(db, org_id: int, total: Decimal = Decimal("1100000")) -> "Invoice":
    """Create a draft invoice and flip it directly to 'sent'."""
    from app.models.invoice import Invoice, InvoiceLine, generate_invoice_number

    subtotal = total / Decimal("1.1")
    tax_amount = total - subtotal

    number = generate_invoice_number(db, date.today().year)
    invoice = Invoice(
        invoice_number=number,
        org_id=org_id,
        status="sent",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        subtotal=subtotal.quantize(Decimal("0.01")),
        tax_rate=Decimal("10.00"),
        tax_amount=tax_amount.quantize(Decimal("0.01")),
        total=total,
    )
    db.add(invoice)
    db.flush()

    line = InvoiceLine(
        invoice_id=invoice.id,
        description="Service fee",
        quantity=Decimal("1"),
        unit_price=subtotal.quantize(Decimal("0.01")),
        line_total=subtotal.quantize(Decimal("0.01")),
    )
    db.add(line)
    db.commit()
    db.refresh(invoice)
    return invoice


def _payment_url(invoice_id: int) -> str:
    return f"/api/invoices/{invoice_id}/payments"


# ── tests ─────────────────────────────────────────────────────────────────────

def test_record_payment_creates_payment_record(db, client, client_org, admin_token):
    """
    POST /api/invoices/{id}/payments creates an InvoicePayment row
    with the supplied fields.
    """
    from app.models.invoice_payment import InvoicePayment

    invoice = _make_sent_invoice(db, client_org.id)

    r = client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "amount": "500000",
            "method": "bank_transfer",
            "reference": "REF-001",
            "note": "First instalment",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["invoice_id"] == invoice.id
    assert Decimal(body["amount"]) == Decimal("500000")
    assert body["method"] == "bank_transfer"
    assert body["reference"] == "REF-001"
    assert body["note"] == "First instalment"
    assert body["paid_by"] is not None

    # Verify row in DB
    payment = db.query(InvoicePayment).filter(
        InvoicePayment.invoice_id == invoice.id
    ).first()
    assert payment is not None
    assert payment.amount == Decimal("500000")


def test_full_payment_marks_invoice_paid(db, client, client_org, admin_token):
    """
    When payment amount >= invoice.total, invoice.status flips to 'paid'.
    """
    from app.models.invoice import Invoice

    invoice = _make_sent_invoice(db, client_org.id, total=Decimal("1000000"))

    r = client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "1000000", "method": "cash"},
    )
    assert r.status_code == 201, r.text

    db.refresh(invoice)
    assert invoice.status == "paid"
    assert invoice.paid_at is not None


def test_partial_payment_does_not_mark_paid(db, client, client_org, admin_token):
    """
    A partial payment (amount < invoice.total) leaves the invoice in 'sent'.
    """
    from app.models.invoice import Invoice

    invoice = _make_sent_invoice(db, client_org.id, total=Decimal("1000000"))

    r = client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "400000", "method": "bank_transfer"},
    )
    assert r.status_code == 201, r.text

    db.refresh(invoice)
    assert invoice.status == "sent"
    assert invoice.paid_at is None


def test_two_partial_payments_sum_to_full_marks_paid(db, client, client_org, admin_token):
    """
    Two partial payments whose sum reaches invoice.total auto-mark the invoice paid.
    """
    from app.models.invoice import Invoice

    invoice = _make_sent_invoice(db, client_org.id, total=Decimal("1000000"))

    client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "600000", "method": "bank_transfer"},
    )
    db.refresh(invoice)
    assert invoice.status == "sent"   # still unpaid after first

    r2 = client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "400000", "method": "cash"},
    )
    assert r2.status_code == 201, r2.text

    db.refresh(invoice)
    assert invoice.status == "paid"


def test_mark_paid_endpoint_creates_payment_record(db, client, client_org, admin_token):
    """
    PUT /api/invoices/{id}/mark-paid preserves payment history by writing
    an InvoicePayment row with method='manual' and amount=invoice.total.
    """
    from app.models.invoice_payment import InvoicePayment

    invoice = _make_sent_invoice(db, client_org.id, total=Decimal("500000"))

    r = client.put(
        f"/api/invoices/{invoice.id}/mark-paid",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text

    db.refresh(invoice)
    assert invoice.status == "paid"

    payment = db.query(InvoicePayment).filter(
        InvoicePayment.invoice_id == invoice.id
    ).first()
    assert payment is not None
    assert payment.method == "manual"
    assert payment.amount == Decimal("500000")
    assert payment.paid_by is not None


def test_payment_list_returns_all_payments(db, client, client_org, admin_token):
    """
    GET /api/invoices/{id}/payments returns every payment in paid_at order.
    """
    invoice = _make_sent_invoice(db, client_org.id, total=Decimal("2000000"))

    client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "800000", "method": "bank_transfer", "reference": "A"},
    )
    client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "700000", "method": "vnpay", "reference": "B"},
    )

    r = client.get(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 2
    references = {p["reference"] for p in items}
    assert references == {"A", "B"}
    amounts = [Decimal(p["amount"]) for p in items]
    assert set(amounts) == {Decimal("800000"), Decimal("700000")}


def test_customer_cannot_record_payment(db, client, client_org, customer_token):
    """
    A customer token receives 403 when attempting to record a payment.
    """
    invoice = _make_sent_invoice(db, client_org.id)

    r = client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"amount": "100000", "method": "cash"},
    )
    assert r.status_code == 403, r.text


def test_customer_cannot_list_payments(db, client, client_org, customer_token):
    """
    A customer token receives 403 when attempting to list payments.
    """
    invoice = _make_sent_invoice(db, client_org.id)

    r = client.get(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 403, r.text


def test_payment_on_draft_invoice_rejected(db, client, client_org, admin_token):
    """
    Recording a payment against a draft invoice returns 400.
    """
    from app.models.invoice import Invoice, generate_invoice_number

    inv = Invoice(
        invoice_number=generate_invoice_number(db, date.today().year),
        org_id=client_org.id,
        status="draft",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        subtotal=Decimal("100000"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("10000"),
        total=Decimal("110000"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    r = client.post(
        _payment_url(inv.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "110000", "method": "cash"},
    )
    assert r.status_code == 400, r.text


def test_invalid_payment_method_rejected(db, client, client_org, admin_token):
    """
    An unrecognised payment method is rejected with 422 (Pydantic validation).
    """
    invoice = _make_sent_invoice(db, client_org.id)

    r = client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "100000", "method": "bitcoin"},
    )
    assert r.status_code == 422, r.text


def test_zero_amount_payment_rejected(db, client, client_org, admin_token):
    """
    Zero or negative amounts are rejected with 422.
    """
    invoice = _make_sent_invoice(db, client_org.id)

    r = client.post(
        _payment_url(invoice.id),
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": "0", "method": "cash"},
    )
    assert r.status_code == 422, r.text
