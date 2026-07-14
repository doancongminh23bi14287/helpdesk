# backend/app/tasks/subscription_checker.py
from app.tasks.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="app.tasks.subscription_checker.check_subscriptions")
def check_subscriptions():
    """Synchronize stored subscription/service state with effective business dates."""
    db = SessionLocal()
    try:
        from app.models.subscription import Subscription
        from app.services.billing import effective_subscription_status
        from app.services.service_sync import sync_service_from_subscription

        subscriptions = db.query(Subscription).filter(
            Subscription.status != "cancelled"
        ).all()

        result = {"trial_to_active": 0, "past_due": 0, "expired": 0}
        for sub in subscriptions:
            previous = sub.status
            effective = effective_subscription_status(sub)
            if effective != "scheduled" and effective != previous:
                sub.status = effective
                if previous == "trial" and effective == "active":
                    result["trial_to_active"] += 1
                elif effective in result:
                    result[effective] += 1
            # Always reconcile the linked service, including legacy rows whose
            # subscription was already marked expired before this checker ran.
            sync_service_from_subscription(
                db,
                sub,
                create_if_missing=False,
                commit=False,
            )

        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
