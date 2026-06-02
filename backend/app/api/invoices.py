from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from math import ceil

from app.database import get_db
from app.models.invoice import Invoice, InvoiceLine
from app.models.organization import Organization
from app.models.user import User
from app.models.team import StaffOrgAssignment
from app.core.deps import get_current_user, require_admin
from app.schemas.invoice import InvoiceCreate, InvoiceOut, InvoiceLineOut
from app.services.invoice_service import (
    create_manual_invoice,
    send_invoice,
    mark_paid,
    cancel_invoice,
)

router = APIRouter(prefix="/api/invoices", tags=["invoices"])
admin_router = APIRouter(prefix="/api/admin/invoices", tags=["admin-invoices"])

VALID_INVOICE_SORT_FIELDS = {"invoice_number", "issue_date", "due_date", "total", "status"}


def _get_accessible_org_ids(user: User, db: Session) -> Optional[List[int]]:
    """None = admin (all orgs). List for staff/customer."""
    if user.role == "admin":
        return None
    if user.role == "customer":
        return [user.org_id]
    rows = db.query(StaffOrgAssignment).filter(StaffOrgAssignment.user_id == user.id).all()
    return [r.org_id for r in rows]


def _enrich_invoice(inv: Invoice, db: Session) -> InvoiceOut:
    """Fetch org name, subscription plan name, and lines for a single invoice."""
    from app.models.subscription import Subscription, SubscriptionPlan

    org = db.query(Organization).filter(Organization.id == inv.org_id).first()
    plan_name = None
    if inv.subscription_id:
        sub = db.query(Subscription).filter(Subscription.id == inv.subscription_id).first()
        if sub:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.subscription_plan_id).first()
            if plan:
                plan_name = plan.name
    lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).all()

    return InvoiceOut(
        **{c.key: getattr(inv, c.key) for c in inv.__table__.columns},
        org_name=org.name if org else None,
        subscription_plan_name=plan_name,
        lines=[InvoiceLineOut.model_validate(l) for l in lines],
    )


def _build_invoices_out(invoices: List[Invoice], db: Session) -> List[InvoiceOut]:
    """Batch-fetch orgs, subscriptions, plans, and lines to avoid N+1 queries."""
    if not invoices:
        return []

    from app.models.subscription import Subscription, SubscriptionPlan

    # Batch fetch orgs
    org_ids = list({inv.org_id for inv in invoices})
    org_map = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}

    # Batch fetch subscriptions
    sub_ids = list({inv.subscription_id for inv in invoices if inv.subscription_id is not None})
    sub_map = {s.id: s for s in db.query(Subscription).filter(Subscription.id.in_(sub_ids)).all()} if sub_ids else {}

    # Batch fetch plans for those subscriptions
    plan_ids = list({s.subscription_plan_id for s in sub_map.values()})
    plan_map = {p.id: p for p in db.query(SubscriptionPlan).filter(SubscriptionPlan.id.in_(plan_ids)).all()} if plan_ids else {}

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
                plan = plan_map.get(sub.subscription_plan_id)
                if plan:
                    plan_name = plan.name
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
    org_ids = _get_accessible_org_ids(user, db)
    q = db.query(Invoice)
    if org_ids is not None:
        q = q.filter(Invoice.org_id.in_(org_ids))
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
    org_ids = _get_accessible_org_ids(user, db)
    if org_ids is not None and inv.org_id not in org_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    return _enrich_invoice(inv, db)


@router.put("/{invoice_id}/send", response_model=InvoiceOut)
def send_invoice_endpoint(
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
    """Mark an invoice as paid (admin only)."""
    try:
        inv = mark_paid(invoice_id=invoice_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_invoice(inv, db)


@router.put("/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice_endpoint(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Cancel an invoice (admin only)."""
    try:
        inv = cancel_invoice(invoice_id=invoice_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_invoice(inv, db)


@admin_router.post("/generate-from-subscriptions", response_model=dict)
def generate_from_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Synchronously run auto_generate_invoices (admin only). Returns {"generated": N}."""
    from app.tasks.invoice_tasks import auto_generate_invoices
    result = auto_generate_invoices()
    return {"generated": result.get("generated", 0)}
