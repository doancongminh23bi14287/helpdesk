from io import BytesIO
from typing import List, Optional
from math import ceil

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.invoice import Invoice, InvoiceLine
from app.models.organization import Organization
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.core.limiter import limiter
from app.core.scoping import scope_invoices, assert_org_access
from app.schemas.invoice import InvoiceCreate, InvoiceOut, InvoiceLineOut, InvoiceLineIn, InvoiceUpdate, CancelPayload, PaymentCreate, PaymentOut
from app.services.invoice_service import (
    create_manual_invoice,
    send_invoice,
    mark_paid,
    cancel_invoice,
)

router = APIRouter(prefix="/api/invoices", tags=["invoices"])
admin_router = APIRouter(prefix="/api/admin/invoices", tags=["admin-invoices"])

VALID_INVOICE_SORT_FIELDS = {"invoice_number", "issue_date", "due_date", "total", "status"}

VALID_INVOICE_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["sent", "cancelled"],
    "sent": ["paid", "overdue", "cancelled"],
    "overdue": ["paid", "cancelled"],
    "paid": [],
    "cancelled": [],
}

LOCKED_STATUSES = {"sent", "paid", "cancelled"}


def _enrich_invoice(inv: Invoice, db: Session) -> InvoiceOut:
    """Fetch org name, subscription plan/item name, and lines for a single invoice."""
    from app.models.subscription import Subscription, SubscriptionPlan
    from app.models.item import Item

    org = db.query(Organization).filter(Organization.id == inv.org_id).first()
    plan_name = None
    if inv.subscription_id:
        sub = db.query(Subscription).filter(Subscription.id == inv.subscription_id).first()
        if sub:
            if sub.subscription_plan_id:
                plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.subscription_plan_id).first()
                plan_name = plan.name if plan else None
            if plan_name is None and sub.item_id:
                item = db.query(Item).filter(Item.id == sub.item_id).first()
                plan_name = item.name if item else None
    lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).all()

    return InvoiceOut(
        **{c.key: getattr(inv, c.key) for c in inv.__table__.columns},
        org_name=org.name if org else None,
        subscription_plan_name=plan_name,
        lines=[InvoiceLineOut.model_validate(l) for l in lines],
    )


def _recalculate_invoice_totals(inv: Invoice, db: Session) -> None:
    """Recompute subtotal/tax_amount/total from current lines. Flushes but does not commit."""
    from decimal import Decimal
    lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).all()
    subtotal = sum((l.line_total for l in lines), Decimal("0"))
    tax_amount = round(subtotal * inv.tax_rate / 100, 2)
    inv.subtotal = subtotal
    inv.tax_amount = tax_amount
    inv.total = subtotal + tax_amount
    db.flush()


def _build_invoices_out(invoices: List[Invoice], db: Session) -> List[InvoiceOut]:
    """Batch-fetch orgs, subscriptions, plans/items, and lines to avoid N+1 queries."""
    if not invoices:
        return []

    from app.models.subscription import Subscription, SubscriptionPlan
    from app.models.item import Item

    # Batch fetch orgs
    org_ids = list({inv.org_id for inv in invoices})
    org_map = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}

    # Batch fetch subscriptions
    sub_ids = list({inv.subscription_id for inv in invoices if inv.subscription_id is not None})
    sub_map = {s.id: s for s in db.query(Subscription).filter(Subscription.id.in_(sub_ids)).all()} if sub_ids else {}

    # Batch fetch plans for those subscriptions
    plan_ids = list({s.subscription_plan_id for s in sub_map.values() if s.subscription_plan_id})
    plan_map = {p.id: p for p in db.query(SubscriptionPlan).filter(SubscriptionPlan.id.in_(plan_ids)).all()} if plan_ids else {}

    # Batch fetch items for subscriptions that use item_id instead of subscription_plan_id
    item_ids = list({s.item_id for s in sub_map.values() if s.item_id and not s.subscription_plan_id})
    item_map = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

    # Batch fetch all invoice lines
    invoice_ids = [inv.id for inv in invoices]
    all_lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id.in_(invoice_ids)).all()
    lines_by_invoice: dict = {}
    for line in all_lines:
        lines_by_invoice.setdefault(line.invoice_id, []).append(line)

    result = []
    for inv in invoices:
        org = org_map.get(inv.org_id)
        plan_name = None
        if inv.subscription_id:
            sub = sub_map.get(inv.subscription_id)
            if sub:
                if sub.subscription_plan_id:
                    plan = plan_map.get(sub.subscription_plan_id)
                    plan_name = plan.name if plan else None
                if plan_name is None and sub.item_id:
                    item = item_map.get(sub.item_id)
                    plan_name = item.name if item else None
        inv_lines = lines_by_invoice.get(inv.id, [])
        result.append(InvoiceOut(
            **{c.key: getattr(inv, c.key) for c in inv.__table__.columns},
            org_name=org.name if org else None,
            subscription_plan_name=plan_name,
            lines=[InvoiceLineOut.model_validate(l) for l in inv_lines],
        ))
    return result


# IMPORTANT: /my must be defined before /{id}
@router.get("/my", response_model=List[InvoiceOut])
def get_my_invoices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Customer sees only their org's invoices."""
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customers only")
    invoices = db.query(Invoice).filter(Invoice.org_id == user.org_id).all()
    return _build_invoices_out(invoices, db)


@router.get("")
def list_invoices(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("issue_date"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List invoices scoped by role."""
    q = db.query(Invoice)
    q = scope_invoices(q, user, db)
    if status:
        q = q.filter(Invoice.status == status)
    # Search: match on invoice_number or org name via join
    if search:
        term = f"%{search}%"
        q = q.join(Organization, Invoice.org_id == Organization.id).filter(
            or_(
                Invoice.invoice_number.ilike(term),
                Organization.name.ilike(term),
            )
        )
    # Sort
    if sort not in VALID_INVOICE_SORT_FIELDS:
        sort = "issue_date"
    sort_col = getattr(Invoice, sort, Invoice.issue_date)
    q = q.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    total = q.count()
    invoices = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": _build_invoices_out(invoices, db),
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice_endpoint(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a manual invoice (admin only)."""
    try:
        inv = create_manual_invoice(
            org_id=payload.org_id,
            lines_data=[l.model_dump() for l in payload.lines],
            db=db,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_invoice(inv, db)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single invoice scoped by role."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    assert_org_access(inv.org_id, user, db)
    return _enrich_invoice(inv, db)


@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download a scoped invoice as a basic PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    assert_org_access(inv.org_id, user, db)
    enriched = _enrich_invoice(inv, db)

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50

    def line(text: str, size: int = 10, step: int = 16):
        nonlocal y
        pdf.setFont("Helvetica", size)
        pdf.drawString(50, y, text[:110])
        y -= step

    line("WorkDesk Invoice", 16, 24)
    line(f"Invoice: {enriched.invoice_number}")
    line(f"Organisation: {enriched.org_name or enriched.org_id}")
    line(f"Status: {enriched.status}")
    line(f"Issue date: {enriched.issue_date}")
    line(f"Due date: {enriched.due_date}")
    y -= 10
    line("Lines", 12, 20)
    for item in enriched.lines:
        line(f"- {item.description}: {item.quantity} x {item.unit_price} = {item.line_total}")
        if y < 90:
            pdf.showPage()
            y = height - 50
    y -= 10
    line(f"Subtotal: {enriched.subtotal}")
    line(f"Tax: {enriched.tax_amount}")
    line(f"Total: {enriched.total}", 12)
    pdf.showPage()
    pdf.save()
    content = buf.getvalue()
    filename = f"invoice-{enriched.invoice_number}.pdf"
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update editable fields on a draft invoice (admin only). Locked once sent/paid/cancelled."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status in LOCKED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invoice cannot be edited in status '{inv.status}'",
        )
    if payload.notes is not None:
        inv.notes = payload.notes
    if payload.due_date is not None:
        inv.due_date = payload.due_date
    if payload.issue_date is not None:
        inv.issue_date = payload.issue_date
    db.commit()
    db.refresh(inv)
    return _enrich_invoice(inv, db)


@router.post("/{invoice_id}/lines", response_model=InvoiceLineOut, status_code=201)
def add_invoice_line(
    invoice_id: int,
    payload: InvoiceLineIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Add a line to a draft invoice (admin only)."""
    from decimal import Decimal as _D
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != "draft":
        raise HTTPException(status_code=422, detail="Invoice lines can only be modified on draft invoices")
    qty = _D(str(payload.quantity))
    price = _D(str(payload.unit_price))
    line = InvoiceLine(
        invoice_id=invoice_id,
        item_id=payload.item_id,
        description=payload.description,
        quantity=qty,
        unit_price=price,
        line_total=qty * price,
    )
    db.add(line)
    db.flush()
    _recalculate_invoice_totals(inv, db)
    db.commit()
    db.refresh(line)
    return InvoiceLineOut.model_validate(line)


@router.put("/{invoice_id}/lines/{line_id}", response_model=InvoiceLineOut)
def update_invoice_line(
    invoice_id: int,
    line_id: int,
    payload: InvoiceLineIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Update a line on a draft invoice (admin only)."""
    from decimal import Decimal as _D
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != "draft":
        raise HTTPException(status_code=422, detail="Invoice lines can only be modified on draft invoices")
    line = db.query(InvoiceLine).filter(InvoiceLine.id == line_id, InvoiceLine.invoice_id == invoice_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    qty = _D(str(payload.quantity))
    price = _D(str(payload.unit_price))
    line.item_id = payload.item_id
    line.description = payload.description
    line.quantity = qty
    line.unit_price = price
    line.line_total = qty * price
    db.flush()
    _recalculate_invoice_totals(inv, db)
    db.commit()
    db.refresh(line)
    return InvoiceLineOut.model_validate(line)


@router.delete("/{invoice_id}/lines/{line_id}", status_code=204)
def delete_invoice_line(
    invoice_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a line from a draft invoice (admin only)."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != "draft":
        raise HTTPException(status_code=422, detail="Invoice lines can only be modified on draft invoices")
    line = db.query(InvoiceLine).filter(InvoiceLine.id == line_id, InvoiceLine.invoice_id == invoice_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    db.delete(line)
    db.flush()
    _recalculate_invoice_totals(inv, db)
    db.commit()


@router.put("/{invoice_id}/send", response_model=InvoiceOut)
@limiter.limit("5/minute")
def send_invoice_endpoint(
    request: Request,
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Send an invoice (admin only)."""
    try:
        inv = send_invoice(invoice_id=invoice_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_invoice(inv, db)


@router.put("/{invoice_id}/mark-paid", response_model=InvoiceOut)
def mark_paid_endpoint(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Mark an invoice as paid (admin only). Creates a 'manual' payment record."""
    try:
        inv = mark_paid(invoice_id=invoice_id, db=db, paid_by_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_invoice(inv, db)


@router.post("/{invoice_id}/payments", response_model=PaymentOut, status_code=201)
def record_payment(
    invoice_id: int,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Record a payment against an invoice (admin only).
    If cumulative payments reach the invoice total, the invoice is auto-marked 'paid'.
    """
    from datetime import datetime as _dt
    from decimal import Decimal
    from sqlalchemy import func
    from app.models.invoice_payment import InvoicePayment

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status not in ("sent", "overdue"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot record payment for invoice with status '{inv.status}'",
        )

    paid_at = payload.paid_at or _dt.utcnow()

    payment = InvoicePayment(
        invoice_id=invoice_id,
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        paid_by=user.id,
        note=payload.note,
        paid_at=paid_at,
    )
    db.add(payment)
    db.flush()

    # Sum all payments including the one just flushed
    paid_total = db.query(func.sum(InvoicePayment.amount)).filter(
        InvoicePayment.invoice_id == invoice_id
    ).scalar() or Decimal("0")

    if paid_total >= inv.total:
        inv.status = "paid"
        inv.paid_at = paid_at

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{invoice_id}/payments", response_model=List[PaymentOut])
def list_payments(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """List all payments recorded against an invoice (admin only)."""
    from app.models.invoice_payment import InvoicePayment

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return (
        db.query(InvoicePayment)
        .filter(InvoicePayment.invoice_id == invoice_id)
        .order_by(InvoicePayment.paid_at)
        .all()
    )


@router.put("/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice_endpoint(
    invoice_id: int,
    payload: Optional[CancelPayload] = Body(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Cancel a draft or sent invoice (admin only). cancel_reason is optional."""
    try:
        reason = payload.cancel_reason if payload else None
        inv = cancel_invoice(invoice_id=invoice_id, db=db, cancel_reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_invoice(inv, db)


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice_endpoint(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a draft or cancelled invoice permanently (admin only)."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status not in ("draft", "cancelled"):
        raise HTTPException(status_code=400, detail="Only draft or cancelled invoices can be deleted")
    db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice_id).delete()
    db.delete(inv)
    db.commit()


@admin_router.post("/generate-from-subscriptions", response_model=dict)
def generate_from_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Synchronously run auto_generate_invoices (admin only). Returns {"generated": N}."""
    from app.tasks.invoice_tasks import auto_generate_invoices
    result = auto_generate_invoices()
    return {"generated": result.get("generated", 0)}
