from datetime import date, timedelta
from typing import List, Optional
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.subscription import SubscriptionPlan, Subscription
from app.models.organization import Organization
from app.models.item import Item
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.core.scoping import scope_subscriptions, assert_org_access
from app.schemas.subscription import SubscriptionCreate, SubscriptionOut
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.service import Service
from app.services.billing import cancel_subscription, create_subscription, effective_subscription_status
from app.services.service_sync import sync_service_from_subscription

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

VALID_SUB_SORT_FIELDS = {"start_date", "next_billing_date", "status", "created_at"}


def _effective_status_condition(status: str):
    """SQL equivalent of effective_subscription_status for list filtering."""
    today = date.today()
    grace_cutoff = today - timedelta(days=7)
    not_cancelled = Subscription.status != "cancelled"
    scheduled = and_(
        not_cancelled,
        Subscription.start_date > today,
    )
    expired = and_(
        not_cancelled,
        ~scheduled,
        or_(
            Subscription.status == "expired",
            Subscription.end_date < today,
            Subscription.next_billing_date < grace_cutoff,
        ),
    )
    trial = and_(
        not_cancelled,
        ~scheduled,
        ~expired,
        Subscription.status == "trial",
        Subscription.trial_end_date.is_not(None),
        Subscription.trial_end_date > today,
    )
    past_due = and_(
        not_cancelled,
        ~scheduled,
        ~expired,
        ~trial,
        Subscription.next_billing_date < today,
    )
    if status == "cancelled":
        return Subscription.status == "cancelled"
    if status == "scheduled":
        return scheduled
    if status == "expired":
        return expired
    if status == "trial":
        return trial
    if status == "past_due":
        return past_due
    if status == "active":
        return and_(not_cancelled, ~scheduled, ~expired, ~trial, ~past_due)
    return Subscription.status == status


def _build_subscriptions_out(subs, db):
    """Batch-fetch plans, items, and orgs to avoid N+1 queries."""
    plan_ids = list({s.subscription_plan_id for s in subs if s.subscription_plan_id})
    item_ids = list({s.item_id for s in subs if s.item_id})
    org_ids = list({s.org_id for s in subs})
    plan_map = {p.id: p for p in db.query(SubscriptionPlan).filter(SubscriptionPlan.id.in_(plan_ids)).all()} if plan_ids else {}
    item_map = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}
    org_map = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}

    result = []
    for s in subs:
        plan = plan_map.get(s.subscription_plan_id)
        item = item_map.get(s.item_id)
        org = org_map.get(s.org_id)
        plan_name = (plan.name if plan else None) or (item.name if item else None)
        values = {c.key: getattr(s, c.key) for c in s.__table__.columns}
        values["status"] = effective_subscription_status(s)
        result.append(SubscriptionOut(
            **values,
            plan_name=plan_name,
            org_name=org.name if org else None,
        ))
    return result


def _enrich_one(sub, db, use_effective: bool = True):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.subscription_plan_id).first() if sub.subscription_plan_id else None
    item = db.query(Item).filter(Item.id == sub.item_id).first() if sub.item_id else None
    org = db.query(Organization).filter(Organization.id == sub.org_id).first()
    plan_name = (plan.name if plan else None) or (item.name if item else None)
    values = {c.key: getattr(sub, c.key) for c in sub.__table__.columns}
    values["status"] = effective_subscription_status(sub) if use_effective else sub.status
    return SubscriptionOut(
        **values,
        plan_name=plan_name,
        org_name=org.name if org else None,
    )


@router.get("/my", response_model=List[SubscriptionOut])
def get_my_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Customer sees only their org's subscriptions."""
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customers only")
    subs = db.query(Subscription).filter(Subscription.org_id == user.org_id).all()
    return _build_subscriptions_out(subs, db)


@router.get("")
def list_subscriptions(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List subscriptions scoped by role."""
    q = db.query(Subscription)
    q = scope_subscriptions(q, user, db)
    if status:
        q = q.filter(_effective_status_condition(status))
    # Search: match on org name via join
    if search:
        term = f"%{search}%"
        q = q.join(Organization, Subscription.org_id == Organization.id).filter(
            Organization.name.ilike(term)
        )
    # Sort
    if sort not in VALID_SUB_SORT_FIELDS:
        sort = "created_at"
    sort_col = getattr(Subscription, sort, Subscription.created_at)
    q = q.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    total = q.count()
    subs = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": _build_subscriptions_out(subs, db),
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


@router.post("", response_model=SubscriptionOut, status_code=201)
def create_subscription_endpoint(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create a new subscription (admin only)."""
    try:
        sub = create_subscription(
            db=db,
            org_id=payload.org_id,
            plan_id=payload.plan_id,
            start_date=payload.start_date,
            billing_cycle=payload.billing_cycle,
            due_days=payload.due_days,
            tax_rate=payload.tax_rate,
            end_date=payload.end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_one(sub, db, use_effective=False)


@router.get("/{sub_id}", response_model=SubscriptionOut)
def get_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single subscription scoped by role."""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    assert_org_access(sub.org_id, user, db)
    return _enrich_one(sub, db, use_effective=True)


@router.delete("/{sub_id}", status_code=204)
def delete_subscription_endpoint(
    sub_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a cancelled subscription permanently (admin only)."""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if sub.status != "cancelled":
        raise HTTPException(status_code=400, detail="Only cancelled subscriptions can be deleted")
    db.query(Invoice).filter(Invoice.subscription_id == sub_id).update({"subscription_id": None})
    db.query(Service).filter(Service.subscription_id == sub_id).update({"subscription_id": None})
    db.delete(sub)
    db.commit()


@router.put("/{sub_id}/cancel", response_model=SubscriptionOut)
def cancel_subscription_endpoint(
    sub_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Cancel a subscription (admin only)."""
    try:
        sub = cancel_subscription(db=db, subscription_id=sub_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sync_service_from_subscription(db, sub, create_if_missing=False)
    return _enrich_one(sub, db, use_effective=False)


@router.delete("/{sub_id}/permanent")
def hard_delete_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Permanently delete a cancelled/expired subscription and its paired service.
    Invoices are kept for accounting; only invoice.subscription_id is nullified.
    Admin only.
    """
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if sub.status not in ("cancelled", "expired"):
        raise HTTPException(
            status_code=400,
            detail="Only cancelled/expired subscriptions can be permanently deleted",
        )

    # a. Collect service IDs before deletion, then clear FKs referencing them
    svc_ids = [row[0] for row in db.query(Service.id).filter(Service.subscription_id == sub_id).all()]
    if svc_ids:
        from app.models.ticket import Ticket
        db.query(Ticket).filter(Ticket.service_id.in_(svc_ids)).update(
            {"service_id": None}, synchronize_session=False
        )
        db.query(Project).filter(Project.service_id.in_(svc_ids)).update(
            {"service_id": None}, synchronize_session=False
        )

    # Delete the paired service(s)
    services_deleted = db.query(Service).filter(
        Service.subscription_id == sub_id
    ).delete(synchronize_session=False)

    # b. Nullify invoice.subscription_id (keep invoices for accounting)
    invoices_kept = db.query(Invoice).filter(
        Invoice.subscription_id == sub_id
    ).update({"subscription_id": None}, synchronize_session=False)

    # c. Nullify project.subscription_id (keep projects)
    db.query(Project).filter(Project.subscription_id == sub_id).update(
        {"subscription_id": None}, synchronize_session=False
    )

    # d. Delete subscription (services FK is already cleared above)
    db.query(Subscription).filter(Subscription.id == sub_id).delete(synchronize_session=False)
    db.commit()

    return {
        "deleted": True,
        "subscription_id": sub_id,
        "service_deleted": services_deleted > 0,
        "invoices_kept": invoices_kept,
    }
