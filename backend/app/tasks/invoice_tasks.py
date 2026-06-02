# backend/app/tasks/invoice_tasks.py
from app.tasks.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="app.tasks.invoice_tasks.check_overdue_invoices")
def check_overdue_invoices():
    """
    Find invoices where status='sent' AND due_date < today.
    Set status='overdue' and notify all admin users.
    Returns {"overdue": N}
    """
    db = SessionLocal()
    try:
        from datetime import date
        from app.models.invoice import Invoice
        from app.models.user import User
        from app.services.notify import create_notification

        today = date.today()

        overdue_invoices = db.query(Invoice).filter(
            Invoice.status == "sent",
            Invoice.due_date < today,
        ).all()

        admins = db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).all()

        for invoice in overdue_invoices:
            invoice.status = "overdue"
            for admin in admins:
                create_notification(
                    db,
                    user_id=admin.id,
                    title=f"Invoice {invoice.invoice_number} overdue",
                    content=f"Invoice {invoice.invoice_number} was due on {invoice.due_date} and is now overdue.",
                    type="info",
                )

        db.commit()
        return {"overdue": len(overdue_invoices)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.invoice_tasks.auto_generate_invoices")
def auto_generate_invoices():
    """
    Find subscriptions where next_billing_date = today AND status='active'.
    For each: create an invoice and advance the subscription billing dates.
    Returns {"generated": N}
    """
    db = SessionLocal()
    try:
        from datetime import date
        from app.models.subscription import Subscription, SubscriptionPlan
        from app.services.invoice_service import create_invoice_from_subscription
        from app.services.billing import compute_period_end, compute_next_billing_date

        today = date.today()

        active_subs = db.query(Subscription).filter(
            Subscription.next_billing_date == today,
            Subscription.status == "active",
        ).all()

        count = 0
        for sub in active_subs:
            create_invoice_from_subscription(sub.id, db)

            plan = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.id == sub.subscription_plan_id
            ).first()

            new_period_start = sub.next_billing_date
            new_period_end = compute_period_end(new_period_start, plan.billing_cycle)
            new_next_billing = compute_next_billing_date(new_period_end)

            sub.current_period_start = new_period_start
            sub.current_period_end = new_period_end
            sub.next_billing_date = new_next_billing

            count += 1

        db.commit()
        return {"generated": count}
    finally:
        db.close()
