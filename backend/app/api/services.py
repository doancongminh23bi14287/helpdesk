# backend/app/api/services.py
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.service import Service
from app.models.user import User
from app.models.subscription import Subscription
from app.core.deps import get_current_user
from app.core.scoping import scope_services
from app.schemas.organization import ServiceOut
from app.services.billing import effective_subscription_status

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=List[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return services scoped to the user's role."""
    query = scope_services(db.query(Service), user, db)
    services = query.order_by(Service.name.asc()).all()
    subscription_ids = {service.subscription_id for service in services if service.subscription_id}
    subscriptions = {
        sub.id: sub
        for sub in db.query(Subscription).filter(Subscription.id.in_(subscription_ids)).all()
    } if subscription_ids else {}

    result = []
    for service in services:
        values = {column.key: getattr(service, column.key) for column in service.__table__.columns}
        subscription = subscriptions.get(service.subscription_id)
        if subscription:
            effective = effective_subscription_status(subscription)
            values["status"] = {
                "trial": "active",
                "active": "active",
                "past_due": "past_due",
                "cancelled": "cancelled",
                "expired": "inactive",
            }[effective]
            values["expiry_date"] = subscription.end_date or subscription.current_period_end
        result.append(ServiceOut(**values))
    return result
