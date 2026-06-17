"""Tests: cancel + hard-delete draft/cancelled invoices (spec items 6-9)."""
from datetime import date, timedelta
from decimal import Decimal


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_invoice(db, org_id: int, status: str = "draft"):
    from app.models.invoice import Invoice, generate_invoice_number
    number = generate_invoice_number(db, date.today().year)
    inv = Invoice(
        invoice_number=number,
        org_id=org_id,
        status=status,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        subtotal=Decimal("100000"),
        tax_rate=Decimal("0.00"),
        tax_amount=Decimal("0"),
        total=Decimal("100000"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


# ── (6) Cancel draft → Cancelled ─────────────────────────────────────────────

def test_cancel_draft_invoice_no_reason(client, db, client_org, admin_token):
    """Cancel a draft invoice without body → 200, status=cancelled, default reason stored."""
    inv = _make_invoice(db, client_org.id, status="draft")
    r = client.put(f"/api/invoices/{inv.id}/cancel", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    db.refresh(inv)
    assert inv.status == "cancelled"
    assert inv.cancel_reason  # non-empty default stored


def test_cancel_draft_invoice_with_reason(client, db, client_org, admin_token):
    """Cancel a draft invoice with explicit reason → stored verbatim."""
    inv = _make_invoice(db, client_org.id, status="draft")
    r = client.put(
        f"/api/invoices/{inv.id}/cancel",
        headers=auth(admin_token),
        json={"cancel_reason": "Nhập sai khách hàng"},
    )
    assert r.status_code == 200, r.text
    db.refresh(inv)
    assert inv.cancel_reason == "Nhập sai khách hàng"


# ── (7) Delete draft → removed from DB ────────────────────────────────────────

def test_delete_draft_invoice(client, db, client_org, admin_token):
    """DELETE /invoices/{id} on a draft invoice removes it and its lines."""
    from app.models.invoice import Invoice, InvoiceLine
    inv = _make_invoice(db, client_org.id, status="draft")
    line = InvoiceLine(
        invoice_id=inv.id,
        description="Test line",
        quantity=Decimal("1"),
        unit_price=Decimal("100000"),
        line_total=Decimal("100000"),
    )
    db.add(line)
    db.commit()
    inv_id = inv.id

    r = client.delete(f"/api/invoices/{inv_id}", headers=auth(admin_token))
    assert r.status_code == 204, r.text

    db.expire_all()
    assert db.query(Invoice).filter(Invoice.id == inv_id).first() is None
    assert db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv_id).count() == 0


# ── (8) Delete paid → 400 ─────────────────────────────────────────────────────

def test_delete_paid_invoice_rejected(client, db, client_org, admin_token):
    """DELETE /invoices/{id} on a paid invoice returns 400."""
    inv = _make_invoice(db, client_org.id, status="paid")
    r = client.delete(f"/api/invoices/{inv.id}", headers=auth(admin_token))
    assert r.status_code == 400, r.text


# ── (9) Non-admin → 403 ───────────────────────────────────────────────────────

def test_delete_invoice_non_admin_forbidden(client, db, client_org, customer_token):
    """DELETE /invoices/{id} by a customer returns 403."""
    inv = _make_invoice(db, client_org.id, status="draft")
    r = client.delete(f"/api/invoices/{inv.id}", headers=auth(customer_token))
    assert r.status_code == 403, r.text
