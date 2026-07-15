# backend/app/api/services.py
import logging
from datetime import datetime, timezone
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.invoice import Invoice
from app.models.invoice_payment import InvoicePayment
from app.models.project import Project
from app.models.service import Service
from app.models.subscription import Subscription
from app.models.ticket import Ticket
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.core.scoping import scope_services
from app.schemas.organization import ServiceOut, ServiceUpdate

router = APIRouter(prefix="/api/services", tags=["services"])
logger = logging.getLogger(__name__)


LifecycleFilter = Literal["active", "archived", "all"]


def _apply_lifecycle_filter(query, lifecycle: LifecycleFilter, user: User):
    if lifecycle == "all" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required to view archived services")
    if lifecycle == "archived":
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required to view archived services")
        return query.filter(Service.is_archived.is_(True))
    if lifecycle == "all":
        return query
    return query.filter(Service.is_archived.is_(False))


def _dependency_map(db: Session, services: list[Service]) -> dict[int, list[str]]:
    if not services:
        return {}

    service_ids = [service.id for service in services]
    subscription_ids = [service.subscription_id for service in services if service.subscription_id]

    ticket_counts = dict(
        db.query(Ticket.service_id, func.count(Ticket.id))
        .filter(Ticket.service_id.in_(service_ids))
        .group_by(Ticket.service_id)
        .all()
    )
    project_counts = dict(
        db.query(Project.service_id, func.count(Project.id))
        .filter(Project.service_id.in_(service_ids))
        .group_by(Project.service_id)
        .all()
    )
    invoice_counts = {}
    payment_counts = {}
    if subscription_ids:
        invoice_counts = dict(
            db.query(Invoice.subscription_id, func.count(Invoice.id))
            .filter(Invoice.subscription_id.in_(subscription_ids))
            .group_by(Invoice.subscription_id)
            .all()
        )
        payment_counts = dict(
            db.query(Invoice.subscription_id, func.count(InvoicePayment.id))
            .join(InvoicePayment, InvoicePayment.invoice_id == Invoice.id)
            .filter(Invoice.subscription_id.in_(subscription_ids))
            .group_by(Invoice.subscription_id)
            .all()
        )

    sub_exists = {
        row[0]
        for row in db.query(Subscription.id).filter(Subscription.id.in_(subscription_ids)).all()
    } if subscription_ids else set()

    dependency_map: dict[int, list[str]] = {}
    for service in services:
        reasons: list[str] = []
        ticket_count = int(ticket_counts.get(service.id, 0) or 0)
        project_count = int(project_counts.get(service.id, 0) or 0)
        if service.subscription_id:
            reasons.append("linked subscription")
            if service.subscription_id in sub_exists:
                invoice_count = int(invoice_counts.get(service.subscription_id, 0) or 0)
                payment_count = int(payment_counts.get(service.subscription_id, 0) or 0)
                if invoice_count:
                    reasons.append(f"{invoice_count} invoice(s)")
                if payment_count:
                    reasons.append(f"{payment_count} payment record(s)")
            else:
                reasons.append("subscription reference")
        if ticket_count:
            reasons.append(f"{ticket_count} ticket(s)")
        if project_count:
            reasons.append(f"{project_count} project(s)")
        dependency_map[service.id] = reasons
    return dependency_map


def _serialize_service(service: Service, dependency_reasons: list[str] | None = None) -> ServiceOut:
    reasons = dependency_reasons or []
    payload = {
        column.key: getattr(service, column.key)
        for column in service.__table__.columns
    }
    payload["monthly_cost"] = float(service.monthly_cost) if service.monthly_cost is not None else None
    payload["can_hard_delete"] = len(reasons) == 0
    payload["dependency_reason"] = None if len(reasons) == 0 else "Service này đã có dữ liệu liên quan và chỉ có thể lưu trữ."
    payload["dependency_details"] = reasons
    return ServiceOut(**payload)


@router.get("", response_model=List[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    lifecycle: LifecycleFilter = Query("active"),
):
    """Return services scoped to the user's role."""
    query = scope_services(db.query(Service), user, db)
    query = _apply_lifecycle_filter(query, lifecycle, user)
    services = query.order_by(Service.name.asc()).all()
    dependency_map = _dependency_map(db, services)
    return [_serialize_service(service, dependency_map.get(service.id)) for service in services]


@router.put("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(service, key, value)

    db.commit()
    db.refresh(service)
    logger.info("service updated service_id=%s user_id=%s", service.id, user.id)
    return _serialize_service(service, _dependency_map(db, [service]).get(service.id))


@router.put("/{service_id}/archive", response_model=ServiceOut)
def archive_service(
    service_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if not service.is_archived:
        service.is_archived = True
        service.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
        service.archived_by_id = user.id
        db.commit()
        db.refresh(service)
        logger.info("service archived service_id=%s user_id=%s", service.id, user.id)

    return _serialize_service(service, _dependency_map(db, [service]).get(service.id))


@router.put("/{service_id}/restore", response_model=ServiceOut)
def restore_service(
    service_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service.is_archived:
        service.is_archived = False
        service.archived_at = None
        service.archived_by_id = None
        db.commit()
        db.refresh(service)
        logger.info("service restored service_id=%s user_id=%s", service.id, user.id)

    return _serialize_service(service, _dependency_map(db, [service]).get(service.id))


@router.delete("/{service_id}/permanent")
def delete_service_permanently(
    service_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    reasons = _dependency_map(db, [service]).get(service.id, [])
    if reasons:
        raise HTTPException(
            status_code=409,
            detail="Service này đã có dữ liệu liên quan và chỉ có thể lưu trữ.",
        )

    db.delete(service)
    db.commit()
    logger.info("service permanently deleted service_id=%s user_id=%s", service_id, user.id)
    return {"deleted": True, "service_id": service_id}
