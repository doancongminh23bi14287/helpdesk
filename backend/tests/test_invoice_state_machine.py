# backend/tests/test_invoice_state_machine.py
"""
Tests for invoice state machine enforcement.

Covers:
  - PUT /api/invoices/{id}           — edit blocked on sent/paid/cancelled
  - PUT /api/invoices/{id}/cancel    — requires cancel_reason body
  - Status transition guards         — VALID_INVOICE_TRANSITIONS enforcement
  - Invoice line CRUD                — draft-only guard on POST/PUT/DELETE /{id}/lines
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_invoice(db, org_id: int, status: str = "draft") -> "Invoice":
    from app.models.invoice import Invoice, InvoiceLine, generate_invoice_number
    from decimal import Decimal

    number = generate_invoice_number(db, date.today().year)
    inv = Invoice(
        invoice_number=number,
        org_id=org_id,
        status=status,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        subtotal=Decimal("100000"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("10000"),
        total=Decimal("110000"),
    )
    db.add(inv)
    db.flush()

    line = InvoiceLine(
        invoice_id=inv.id,
        description="Service",
        quantity=Decimal("1"),
        unit_price=Decimal("100000"),
        line_total=Decimal("100000"),
    )
    db.add(line)
    db.commit()
    db.refresh(inv)
    return inv


# ── edit endpoint guard ───────────────────────────────────────────────────────

def test_can_edit_draft_invoice(db, client, client_org, admin_token):
    """PUT /{id} succeeds on a draft invoice — updates notes and due_date."""
    inv = _make_invoice(db, client_org.id, status="draft")
    new_due = (date.today() + timedelta(days=30)).isoformat()

    r = client.put(
        f"/api/invoices/{inv.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "Updated note", "due_date": new_due},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["notes"] == "Updated note"
    assert body["due_date"] == new_due


def test_cannot_edit_sent_invoice(db, client, client_org, admin_token):
    """PUT /{id} returns 422 when invoice status is 'sent'."""
    inv = _make_invoice(db, client_org.id, status="sent")

    r = client.put(
        f"/api/invoices/{inv.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "should be rejected"},
    )
    assert r.status_code == 422, r.text


def test_cannot_edit_paid_invoice(db, client, client_org, admin_token):
    """PUT /{id} returns 422 when invoice status is 'paid'."""
    inv = _make_invoice(db, client_org.id, status="paid")

    r = client.put(
        f"/api/invoices/{inv.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "should be rejected"},
    )
    assert r.status_code == 422, r.text


def test_cannot_edit_cancelled_invoice(db, client, client_org, admin_token):
    """PUT /{id} returns 422 when invoice status is 'cancelled'."""
    inv = _make_invoice(db, client_org.id, status="cancelled")

    r = client.put(
        f"/api/invoices/{inv.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "should be rejected"},
    )
    assert r.status_code == 422, r.text


# ── cancel with reason ────────────────────────────────────────────────────────

def test_cancel_draft_no_body_succeeds(db, client, client_org, admin_token):
    """PUT /{id}/cancel without a body now works — defaults cancel_reason to 'Cancelled by admin'."""
    inv = _make_invoice(db, client_org.id, status="draft")

    r = client.put(
        f"/api/invoices/{inv.id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "Cancelled by admin"


def test_cancel_with_reason_succeeds(db, client, client_org, admin_token):
    """PUT /{id}/cancel with cancel_reason flips status and stores the reason."""
    inv = _make_invoice(db, client_org.id, status="draft")

    r = client.put(
        f"/api/invoices/{inv.id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"cancel_reason": "Duplicate invoice created by mistake"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "Duplicate invoice created by mistake"

    db.refresh(inv)
    assert inv.status == "cancelled"
    assert inv.cancel_reason == "Duplicate invoice created by mistake"


def test_cancel_paid_invoice_rejected(db, client, client_org, admin_token):
    """Cancelling a paid invoice returns 400 (invalid transition)."""
    inv = _make_invoice(db, client_org.id, status="paid")

    r = client.put(
        f"/api/invoices/{inv.id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"cancel_reason": "trying to cancel paid invoice"},
    )
    assert r.status_code == 400, r.text


# ── status transitions via existing endpoints ─────────────────────────────────

def test_valid_transition_draft_to_sent(db, client, client_org, admin_token):
    """PUT /{id}/send successfully transitions a draft invoice to 'sent'."""
    inv = _make_invoice(db, client_org.id, status="draft")

    r = client.put(
        f"/api/invoices/{inv.id}/send",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent"

    db.refresh(inv)
    assert inv.status == "sent"


def test_cannot_transition_paid_to_draft(db, client, client_org, admin_token):
    """PUT /{id} cannot set status — no status field in InvoiceUpdate (edit is blocked anyway)."""
    inv = _make_invoice(db, client_org.id, status="paid")

    # Attempt to edit (which is locked) — 422
    r = client.put(
        f"/api/invoices/{inv.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "trying to re-open paid invoice"},
    )
    assert r.status_code == 422, r.text

    db.refresh(inv)
    assert inv.status == "paid"  # unchanged


def test_cannot_transition_cancelled_to_paid(db, client, client_org, admin_token):
    """PUT /{id}/mark-paid on a cancelled invoice returns 400."""
    inv = _make_invoice(db, client_org.id, status="cancelled")

    r = client.put(
        f"/api/invoices/{inv.id}/mark-paid",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400, r.text


# ── invoice line CRUD guard ───────────────────────────────────────────────────

def test_add_line_to_draft_succeeds(db, client, client_org, admin_token):
    """POST /{id}/lines adds a line and recalculates totals on a draft invoice."""
    inv = _make_invoice(db, client_org.id, status="draft")
    original_total = inv.total

    r = client.post(
        f"/api/invoices/{inv.id}/lines",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"description": "Extra service", "quantity": "2", "unit_price": "50000"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["description"] == "Extra service"
    assert Decimal(body["line_total"]) == Decimal("100000")

    db.refresh(inv)
    assert inv.total > original_total


def test_add_line_to_sent_invoice_rejected(db, client, client_org, admin_token):
    """POST /{id}/lines returns 422 when invoice is 'sent'."""
    inv = _make_invoice(db, client_org.id, status="sent")

    r = client.post(
        f"/api/invoices/{inv.id}/lines",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"description": "New line", "quantity": "1", "unit_price": "50000"},
    )
    assert r.status_code == 422, r.text


def test_update_line_on_draft_succeeds(db, client, client_org, admin_token):
    """PUT /{id}/lines/{line_id} updates the line and recalculates totals."""
    from app.models.invoice import InvoiceLine
    inv = _make_invoice(db, client_org.id, status="draft")
    line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).first()

    r = client.put(
        f"/api/invoices/{inv.id}/lines/{line.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"description": "Revised service", "quantity": "3", "unit_price": "20000"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["description"] == "Revised service"
    assert Decimal(body["line_total"]) == Decimal("60000")


def test_update_line_on_sent_invoice_rejected(db, client, client_org, admin_token):
    """PUT /{id}/lines/{line_id} returns 422 when invoice is 'sent'."""
    from app.models.invoice import InvoiceLine
    inv = _make_invoice(db, client_org.id, status="sent")
    line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).first()

    r = client.put(
        f"/api/invoices/{inv.id}/lines/{line.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"description": "Revised", "quantity": "1", "unit_price": "50000"},
    )
    assert r.status_code == 422, r.text


def test_delete_line_from_draft_succeeds(db, client, client_org, admin_token):
    """DELETE /{id}/lines/{line_id} removes the line from a draft invoice."""
    from app.models.invoice import InvoiceLine
    inv = _make_invoice(db, client_org.id, status="draft")
    line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).first()

    r = client.delete(
        f"/api/invoices/{inv.id}/lines/{line.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204, r.text

    remaining = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).all()
    assert len(remaining) == 0


def test_delete_line_from_sent_invoice_rejected(db, client, client_org, admin_token):
    """DELETE /{id}/lines/{line_id} returns 422 when invoice is 'sent'."""
    from app.models.invoice import InvoiceLine
    inv = _make_invoice(db, client_org.id, status="sent")
    line = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).first()

    r = client.delete(
        f"/api/invoices/{inv.id}/lines/{line.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422, r.text
