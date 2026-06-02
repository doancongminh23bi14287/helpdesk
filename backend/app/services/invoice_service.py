# backend/app/services/invoice_service.py
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLine, generate_invoice_number
from app.models.organization import Organization
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.services.notify import create_notification


def create_invoice_from_subscription(subscription_id: int, db: Session) -> Invoice:
    """
    Create a draft invoice from a subscription's current period.
    """
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if sub is None:
        raise ValueError(f"Subscription {subscription_id} not found")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.subscription_plan_id).first()

    today = date.today()
    invoice_number = generate_invoice_number(db, today.year)
    issue_date = today
    due_date = today + timedelta(days=15)

    unit_price = Decimal(str(sub.unit_price))
    quantity = Decimal("1")
    line_total = unit_price * quantity

    subtotal = line_total
    tax_amount = round(subtotal * Decimal("0.10"), 2)
    total = subtotal + tax_amount

    invoice = Invoice(
        invoice_number=invoice_number,
        org_id=sub.org_id,
        subscription_id=subscription_id,
        status="draft",
        issue_date=issue_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_rate=Decimal("10.00"),
        tax_amount=tax_amount,
        total=total,
    )
    db.add(invoice)
    db.flush()

    line = InvoiceLine(
        invoice_id=invoice.id,
        item_id=None,
        description=f"{plan.name} — {sub.current_period_start} to {sub.current_period_end}",
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
    )
    db.add(line)

    db.commit()
    db.refresh(invoice)
    return invoice


def create_manual_invoice(
    org_id: int,
    lines_data: list,
    db: Session,
    notes: str | None = None,
) -> Invoice:
    """
    Create a manual draft invoice for an org.
    lines_data = [{"item_id": int|None, "description": str, "quantity": Decimal, "unit_price": Decimal}]
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise ValueError(f"Organization {org_id} not found")

    today = date.today()
    invoice_number = generate_invoice_number(db, today.year)
    issue_date = today
    due_date = today + timedelta(days=15)

    subtotal = Decimal("0.00")
    invoice_lines = []
    for ld in lines_data:
        quantity = Decimal(str(ld["quantity"]))
        unit_price = Decimal(str(ld["unit_price"]))
        line_total = quantity * unit_price
        subtotal += line_total
        invoice_lines.append({
            "item_id": ld.get("item_id"),
            "description": ld["description"],
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        })

    tax_amount = round(subtotal * Decimal("0.10"), 2)
    total = subtotal + tax_amount

    invoice = Invoice(
        invoice_number=invoice_number,
        org_id=org_id,
        subscription_id=None,
        status="draft",
        issue_date=issue_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_rate=Decimal("10.00"),
        tax_amount=tax_amount,
        total=total,
        notes=notes,
    )
    db.add(invoice)
    db.flush()

    for ld in invoice_lines:
        line = InvoiceLine(
            invoice_id=invoice.id,
            item_id=ld["item_id"],
            description=ld["description"],
            quantity=ld["quantity"],
            unit_price=ld["unit_price"],
            line_total=ld["line_total"],
        )
        db.add(line)

    db.commit()
    db.refresh(invoice)
    return invoice


def send_invoice(invoice_id: int, db: Session) -> Invoice:
    """
    Transition invoice from 'draft' to 'sent' and notify all customer users of the org.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    if invoice.status != "draft":
        raise ValueError(f"Invoice {invoice_id} has status '{invoice.status}', expected 'draft'")

    invoice.status = "sent"
    db.flush()

    customers = db.query(User).filter(
        User.org_id == invoice.org_id,
        User.role == "customer",
        User.is_active == True,
    ).all()

    for user in customers:
        create_notification(
            db,
            user_id=user.id,
            title=f"Invoice {invoice.invoice_number} sent",
            content=f"Invoice {invoice.invoice_number} for ₫{invoice.total:,.0f} is due on {invoice.due_date}",
            type="info",
        )

    db.commit()
    db.refresh(invoice)
    return invoice


def mark_paid(invoice_id: int, db: Session) -> Invoice:
    """
    Transition invoice from 'sent' or 'overdue' to 'paid' and notify admin users.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    if invoice.status not in ("sent", "overdue"):
        raise ValueError(
            f"Invoice {invoice_id} has status '{invoice.status}', expected 'sent' or 'overdue'"
        )

    invoice.status = "paid"
    invoice.paid_at = datetime.utcnow()
    db.flush()

    admins = db.query(User).filter(
        User.role == "admin",
        User.is_active == True,
    ).all()

    for admin in admins:
        create_notification(
            db,
            user_id=admin.id,
            title=f"Invoice {invoice.invoice_number} paid",
            content=f"Payment received for invoice {invoice.invoice_number}",
            type="info",
        )

    db.commit()
    db.refresh(invoice)
    return invoice


def cancel_invoice(invoice_id: int, db: Session) -> Invoice:
    """
    Transition invoice from 'draft' or 'sent' to 'cancelled'.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    if invoice.status not in ("draft", "sent"):
        raise ValueError(
            f"Invoice {invoice_id} has status '{invoice.status}', expected 'draft' or 'sent'"
        )

    invoice.status = "cancelled"
    db.commit()
    db.refresh(invoice)
    return invoice
