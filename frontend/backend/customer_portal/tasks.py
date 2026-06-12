"""
customer_portal/tasks.py
Scheduled background tasks registered in hooks.py → scheduler_events.

Each function is a thin orchestrator — business logic lives in services/.
"""
from datetime import date, timedelta
import frappe

from customer_portal.repositories.service_repository import get_hosting_plans_expiring_on
from customer_portal.repositories.customer_repository import get_customer_email
from customer_portal.services.notification_service import notify_expiry_warning


# ── Email polling ─────────────────────────────────────────────────────────────

def poll_email():
    """
    Poll the configured IMAP inbox for new support emails.
    Runs on the "all" scheduler (every ~5 minutes in Frappe).
    Gracefully no-ops if email piping is not configured.
    """
    from customer_portal.email.listener import poll_inbound_email
    poll_inbound_email()


# ── Expiry notifications ──────────────────────────────────────────────────────

def send_expiry_notifications():
    """
    Email customers when a Hosting Plan is 7 or 30 days from expiry.
    Runs daily via hooks.py.
    """
    today = date.today()
    warning_thresholds = [7, 30]

    for days in warning_thresholds:
        target_date = str(today + timedelta(days=days))
        plans = get_hosting_plans_expiring_on(target_date)

        for plan in plans:
            customer_email = get_customer_email(plan.customer)
            if not customer_email:
                frappe.logger().warning(
                    f"No email found for customer '{plan.customer}' — skipping expiry notice for {plan.name}"
                )
                continue

            try:
                notify_expiry_warning(
                    customer_email=customer_email,
                    plan_name=plan.name,
                    plan_type="Hosting Plan",
                    expiry_date=plan.expiry_date,
                    days_remaining=days,
                )
            except Exception as exc:
                frappe.log_error(str(exc), f"Expiry notification failed: {plan.name}")
