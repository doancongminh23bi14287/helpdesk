# backend/app/services/invoice_service.py
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLine, generate_invoice_number
from app.models.organization import Organization
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.item import Item
from app.models.user import User
from app.services.notify import create_notification


def create_invoice_from_subscription(subscription_id: int, db: Session) -> Invoice:
    """
    Create a draft invoice from a subscription's current period.
    Supports both item-based subs (item_id set) and plan-based subs (subscription_plan_id set).
    """
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if sub is None:
        raise ValueError(f"Subscription {subscription_id} not found")

    # Resolve name and tax_rate from whichever source this subscription uses
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == sub.subscription_plan_id
    ).first() if sub.subscription_plan_id else None

    item = db.query(Item).filter(
        Item.id == sub.item_id
    ).first() if sub.item_id else None

    display_name = (item.name if item else None) or (plan.name if plan else f"Subscription #{sub.id}")
    plan_tax_rate = Decimal(str(sub.tax_rate)) if getattr(sub, 'tax_rate', None) is not None else Decimal("0")

    today = date.today()
    invoice_number = generate_invoice_number(db, today.year)
    issue_date = today
    due_days = getattr(sub, 'due_days', 15) or 15
    due_date = issue_date + timedelta(days=due_days)

    unit_price = Decimal(str(sub.unit_price))
    quantity = Decimal("1")
    line_total = unit_price * quantity

    subtotal = line_total
    tax_amount = round(subtotal * plan_tax_rate / 100, 2)
    total = subtotal + tax_amount

    invoice = Invoice(
        invoice_number=invoice_number,
        org_id=sub.org_id,
        subscription_id=subscription_id,
        status="draft",
        issue_date=issue_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_rate=plan_tax_rate,
        tax_amount=tax_amount,
        total=total,
    )
    db.add(invoice)
    db.flush()

    line = InvoiceLine(
        invoice_id=invoice.id,
        item_id=sub.item_id,
        description=f"{display_name} — {sub.current_period_start} to {sub.current_period_end}",
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

    tax_amount = Decimal("0.00")
    total = subtotal + tax_amount

    invoice = Invoice(
        invoice_number=invoice_number,
        org_id=org_id,
        subscription_id=None,
        status="draft",
        issue_date=issue_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_rate=Decimal("0.00"),
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


def _fmt_vnd(amount) -> str:
    return f"{round(amount):,}".replace(",", ".") + " ₫"


def send_invoice(invoice_id: int, db: Session) -> Invoice:
    """
    Enqueue invoice email for delivery via the outbox pattern.

    Atomically marks invoice as 'sent' and writes one EmailOutbox record per
    recipient. Actual SMTP delivery is handled by the process_email_outbox
    Celery task, which retries on failure without touching invoice state.
    """
    from app.services.email_templates import render_template
    from app.models.email_outbox import EmailOutbox

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    if invoice.status not in ("draft", "sent"):
        raise ValueError(f"Invoice {invoice_id} has status '{invoice.status}', expected 'draft' or 'sent'")

    org = db.query(Organization).filter(Organization.id == invoice.org_id).first()
    org_name = org.name if org else f"org#{invoice.org_id}"

    # Resolve plan/item name for plan_section
    plan_name = None
    if invoice.subscription_id:
        sub = db.query(Subscription).filter(Subscription.id == invoice.subscription_id).first()
        if sub:
            if sub.subscription_plan_id:
                plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.subscription_plan_id).first()
                plan_name = plan.name if plan else None
            if plan_name is None and sub.item_id:
                item = db.query(Item).filter(Item.id == sub.item_id).first()
                plan_name = item.name if item else None

    plan_section = ""
    if plan_name:
        plan_section = (
            '<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;'
            'padding:10px 16px;margin-bottom:16px;font-size:13px;color:#0c4a6e">'
            f'<strong>Gói dịch vụ:</strong> {plan_name}</div>'
        )

    # Build line rows
    lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice_id).all()
    rows = []
    for ln in lines:
        rows.append(
            '<tr>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#374151">{ln.description}</td>'
            f'<td style="text-align:right;padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280">{int(ln.quantity):g}</td>'
            f'<td style="text-align:right;padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280">{_fmt_vnd(ln.unit_price)}</td>'
            f'<td style="text-align:right;padding:10px 12px;border-bottom:1px solid #e5e7eb;font-weight:600;color:#111">{_fmt_vnd(ln.line_total)}</td>'
            '</tr>'
        )
    lines_html = "\n".join(rows) if rows else (
        '<tr><td colspan="4" style="padding:12px;color:#9ca3af;text-align:center">—</td></tr>'
    )

    notes_section = ""
    if invoice.notes:
        notes_section = (
            '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;'
            'padding:12px 16px;margin-bottom:24px;font-size:13px;color:#374151">'
            '<p style="margin:0 0 4px;font-weight:600;color:#111">Ghi chú:</p>'
            f'<p style="margin:0">{invoice.notes}</p></div>'
        )

    body_html = render_template(
        "invoice.html",
        invoice_number=invoice.invoice_number,
        org_name=org_name,
        issue_date=invoice.issue_date.strftime("%d/%m/%Y"),
        due_date=invoice.due_date.strftime("%d/%m/%Y"),
        plan_section=plan_section,
        lines_html=lines_html,
        subtotal_fmt=_fmt_vnd(invoice.subtotal),
        tax_rate=f"{invoice.tax_rate:g}",
        tax_amount_fmt=_fmt_vnd(invoice.tax_amount),
        total_fmt=_fmt_vnd(invoice.total),
        notes_section=notes_section,
    )
    body_text = (
        f"Hóa đơn {invoice.invoice_number} — {org_name}\n"
        f"Ngày phát hành: {invoice.issue_date}\n"
        f"Hạn thanh toán: {invoice.due_date}\n"
        f"Tổng cộng: {_fmt_vnd(invoice.total)}\n"
        f"Liên hệ: ticket@osd.vn"
    )
    subject = f"[OSD] Hóa đơn {invoice.invoice_number} — {org_name}"

    # Collect recipients (org contact + customer users), deduplicated
    recipients = set()
    if org and org.contact_email:
        recipients.add(org.contact_email)
    customers = db.query(User).filter(
        User.org_id == invoice.org_id,
        User.role == "customer",
        User.is_active == True,
    ).all()
    for u in customers:
        if u.email:
            recipients.add(u.email)

    # Enqueue one outbox record per recipient — committed atomically with the
    # invoice status transition below so delivery state and invoice state
    # never diverge even if the process dies between the two writes.
    for to_addr in recipients:
        outbox = EmailOutbox(
            email_type="invoice",
            recipient_email=to_addr,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            status="pending",
            related_type="invoice",
            related_id=invoice.id,
        )
        db.add(outbox)

    # Transition state
    invoice.status = "sent"
    if invoice.sent_at is None:
        invoice.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()

    for u in customers:
        create_notification(
            db,
            user_id=u.id,
            title=f"Invoice {invoice.invoice_number} sent",
            content=f"Invoice {invoice.invoice_number} for {_fmt_vnd(invoice.total)} is due on {invoice.due_date}",
            type="info",
        )

    db.commit()
    db.refresh(invoice)
    return invoice


def mark_paid(invoice_id: int, db: Session, paid_by_id: int | None = None) -> Invoice:
    """
    Transition invoice from 'sent' or 'overdue' to 'paid'.
    Creates an InvoicePayment record with method='manual' so payment history
    is preserved even when using the legacy one-click endpoint.
    """
    from app.models.invoice_payment import InvoicePayment

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    if invoice.status not in ("sent", "overdue"):
        raise ValueError(
            f"Invoice {invoice_id} has status '{invoice.status}', expected 'sent' or 'overdue'"
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    invoice.status = "paid"
    invoice.paid_at = now
    db.flush()

    payment = InvoicePayment(
        invoice_id=invoice.id,
        amount=invoice.total,
        method="manual",
        paid_by=paid_by_id,
        paid_at=now,
    )
    db.add(payment)

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


def cancel_invoice(invoice_id: int, db: Session, cancel_reason: str | None = None) -> Invoice:
    """
    Transition invoice from 'draft' or 'sent' to 'cancelled'.
    cancel_reason is required and stored on the invoice for audit trail.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    if invoice.status not in ("draft", "sent"):
        raise ValueError(
            f"Invoice {invoice_id} has status '{invoice.status}', expected 'draft' or 'sent'"
        )

    invoice.status = "cancelled"
    invoice.cancel_reason = (cancel_reason.strip() if cancel_reason and cancel_reason.strip() else "Cancelled by admin")
    db.commit()
    db.refresh(invoice)
    return invoice
