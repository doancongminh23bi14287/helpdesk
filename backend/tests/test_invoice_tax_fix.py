# backend/tests/test_invoice_tax_fix.py
"""
Verify that create_manual_invoice defaults tax_rate and tax_amount to 0,
not 10% (regression guard for Fix B1).
"""
from decimal import Decimal


def test_manual_invoice_tax_rate_defaults_to_zero(db, client_org):
    """create_manual_invoice must default tax_rate to 0, not 10."""
    from app.services.invoice_service import create_manual_invoice

    invoice = create_manual_invoice(
        org_id=client_org.id,
        lines_data=[
            {
                "item_id": None,
                "description": "Support service",
                "quantity": Decimal("1"),
                "unit_price": Decimal("1000000"),
            }
        ],
        db=db,
    )

    assert invoice.tax_rate == Decimal("0.00"), (
        f"Expected tax_rate=0.00, got {invoice.tax_rate}"
    )
    assert invoice.tax_amount == Decimal("0.00"), (
        f"Expected tax_amount=0.00, got {invoice.tax_amount}"
    )
    assert invoice.total == Decimal("1000000.00"), (
        f"Expected total=1000000.00, got {invoice.total}"
    )
    assert invoice.subtotal == Decimal("1000000.00"), (
        f"Expected subtotal=1000000.00, got {invoice.subtotal}"
    )
