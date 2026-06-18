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
    Pass 1: subscriptions where next_billing_date <= today (renewal) — generate + advance dates.
    Pass 2: active subscriptions with no non-cancelled invoice yet — generate initial invoice.
    Returns {"generated": N}
    """
    db = SessionLocal()
    try:
        from datetime import date
        from app.models.subscription import Subscription
        from app.models.invoice import Invoice
        from app.services.invoice_service import create_invoice_from_subscription
        from app.services.billing import compute_period_end, compute_next_billing_date

        today = date.today()
        count = 0
        handled_ids: set = set()

        # --- Pass 1: renewal billing ---
        renewal_subs = db.query(Subscription).filter(
            Subscription.next_billing_date <= today,
            Subscription.status == "active",
        ).all()

        for sub in renewal_subs:
            # skip_locked=True: if another worker already holds this row's lock,
            # skip rather than wait — prevents two workers creating invoices for
            # the same subscription in a concurrent Celery execution.
            sub_locked = db.query(Subscription).filter(
                Subscription.id == sub.id,
            ).with_for_update(skip_locked=True).first()
            if sub_locked is None:
                continue

            # Idempotency: skip if a non-cancelled invoice already exists for this
            # billing period (issue_date >= next_billing_date catches same-day re-runs).
            existing = db.query(Invoice).filter(
                Invoice.subscription_id == sub_locked.id,
                Invoice.issue_date >= sub_locked.next_billing_date,
                Invoice.status != "cancelled",
            ).first()
            if existing:
                handled_ids.add(sub_locked.id)
                continue

            create_invoice_from_subscription(sub_locked.id, db)

            new_period_start = sub_locked.next_billing_date
            cycle = getattr(sub_locked, "billing_cycle", None) or "monthly"
            new_period_end = compute_period_end(new_period_start, cycle)
            new_next_billing = compute_next_billing_date(new_period_end)

            sub_locked.current_period_start = new_period_start
            sub_locked.current_period_end = new_period_end
            sub_locked.next_billing_date = new_next_billing

            handled_ids.add(sub_locked.id)
            count += 1

        # --- Pass 2: initial invoices for subscriptions that have none yet ---
        invoiced_sub_ids = {
            row[0]
            for row in db.query(Invoice.subscription_id).filter(
                Invoice.subscription_id.isnot(None),
                Invoice.status.notin_(["cancelled"]),
            ).all()
        }

        uninvoiced_subs = db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.id.notin_(invoiced_sub_ids | handled_ids),
        ).all()

        for sub in uninvoiced_subs:
            create_invoice_from_subscription(sub.id, db)
            count += 1

        db.commit()
        return {"generated": count}
    finally:
        db.close()
