# backend/app/tasks/expiry_notifier.py
from app.tasks.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="app.tasks.expiry_notifier.notify_expiring")
def notify_expiring():
    """
    Daily at 09:00 UTC. Notifies orgs about subscriptions expiring within 7 days.

    For each active subscription where next_billing_date is between today and today+7 days:
    - Find all admin users (role='admin')
    - Send notification: title="Subscription expiring soon",
      content=f"Subscription #{sub.id} for org {org.name} expires on {sub.next_billing_date}"
    - Use dedup: skip if a notification with same ref content was sent today
      (check Notification.content LIKE f"Subscription #{sub.id}%" AND created_at >= today midnight)

    Returns dict: {"notified": N}
    """
    db = SessionLocal()
    try:
        from app.models.subscription import Subscription
        from app.models.organization import Organization
        from app.models.notification import Notification
        from app.models.user import User
        from app.services.notify import create_notification
        from datetime import date, timedelta, datetime

        today = date.today()
        window_end = today + timedelta(days=7)
        today_midnight = datetime(today.year, today.month, today.day)

        expiring_subs = db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.next_billing_date >= today,
            Subscription.next_billing_date <= window_end,
        ).all()

        notified = 0

        admins = db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).all()

        org_ids = {sub.org_id for sub in expiring_subs}
        org_map = {o.id: o for o in db.query(Organization).filter(Organization.id.in_(org_ids)).all()} if org_ids else {}

        for sub in expiring_subs:
            org = org_map.get(sub.org_id)
            org_name = org.name if org else f"org#{sub.org_id}"

            for admin in admins:
                already_notified = db.query(Notification).filter(
                    Notification.user_id == admin.id,
                    Notification.content.like(f"Subscription #{sub.id}%"),
                    Notification.created_at >= today_midnight,
                ).first()

                if not already_notified:
                    create_notification(
                        db,
                        user_id=admin.id,
                        title="Subscription expiring soon",
                        content=f"Subscription #{sub.id} for org {org_name} expires on {sub.next_billing_date}",
                        type="expiry",
                    )
                    notified += 1

        db.commit()
        return {"notified": notified}
    finally:
        db.close()
