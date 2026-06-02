# backend/app/tasks/subscription_checker.py
from app.tasks.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="app.tasks.subscription_checker.check_subscriptions")
def check_subscriptions():
    """
    Daily at 08:00 UTC. Transitions subscription statuses based on today's date.

    Transitions:
    1. trial → active: when today >= trial_end_date (trial ended, move to active)
    2. active/trial/past_due → expired: when today > next_billing_date + 7 days grace period
       (i.e., next_billing_date < today - 7 days)
    3. active → past_due: when today > next_billing_date (overdue, not yet in grace exhaustion)
       (i.e., next_billing_date < today AND next_billing_date >= today - 7 days)

    Returns dict: {"trial_to_active": N, "past_due": N, "expired": N}
    """
    db = SessionLocal()
    try:
        from app.models.subscription import Subscription
        from datetime import date, timedelta

        today = date.today()
        grace_cutoff = today - timedelta(days=7)

        subscriptions = db.query(Subscription).filter(
            Subscription.status.notin_(["cancelled", "expired"])
        ).all()

        trial_to_active = 0
        past_due = 0
        expired = 0

        for sub in subscriptions:
            if sub.status == "trial" and sub.trial_end_date is not None and today >= sub.trial_end_date:
                sub.status = "active"
                trial_to_active += 1
            elif sub.next_billing_date < grace_cutoff:
                sub.status = "expired"
                expired += 1
            elif sub.next_billing_date < today:
                sub.status = "past_due"
                past_due += 1

        db.commit()
        return {"trial_to_active": trial_to_active, "past_due": past_due, "expired": expired}
    finally:
        db.close()
