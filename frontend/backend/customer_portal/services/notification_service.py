"""
Notification service — dispatches real-time events and persists notification logs.
Extracted from ticket_hooks.py so multiple callers can share the same logic.
"""
import frappe

# Status → human-readable message shown to the customer
_STATUS_MESSAGES = {
    "Replied":  "A support agent has replied to your ticket.",
    "Resolved": "Your ticket has been marked as resolved.",
    "Closed":   "Your ticket has been closed.",
    "Pending":  "Your ticket is pending a response from you.",
}


def notify_ticket_status_change(ticket, new_status: str):
    """
    Called when a ticket status changes to a customer-visible state.
    Publishes a WebSocket event and creates a persistent Notification Log.
    """
    message = _STATUS_MESSAGES.get(new_status)
    if not message or not ticket.raised_by or ticket.raised_by == "Guest":
        return

    _publish_realtime(ticket.raised_by, ticket.name, ticket.subject, new_status, message)
    _create_notification_log(ticket.raised_by, ticket.name, new_status, message)


def notify_agent_reply(ticket, comment):
    """
    Called when a staff member posts a public reply.
    Notifies the ticket owner that someone responded.
    """
    notify_ticket_status_change(ticket, "Replied")


def notify_expiry_warning(customer_email: str, plan_name: str, plan_type: str, expiry_date, days_remaining: int):
    """Send an email warning about an upcoming service expiry."""
    frappe.sendmail(
        recipients=[customer_email],
        subject=f"[Action Required] {plan_type} '{plan_name}' expires in {days_remaining} days",
        message=_expiry_email_body(plan_name, plan_type, expiry_date, days_remaining),
        now=True,
    )
    frappe.logger().info(f"Expiry notification sent: {plan_name} ({plan_type}) → {customer_email}")


# ── Private helpers ────────────────────────────────────────────────────────────

def _publish_realtime(user: str, ticket_id: str, subject: str, status: str, message: str):
    try:
        frappe.publish_realtime(
            event="ticket_update",
            message={
                "ticket_id": ticket_id,
                "subject": subject,
                "status": status,
                "message": message,
            },
            user=user,
        )
    except Exception:
        pass  # WebSocket failure must never break the request


def _create_notification_log(user: str, ticket_id: str, status: str, message: str):
    try:
        log = frappe.new_doc("Notification Log")
        log.subject = f"Ticket #{ticket_id}: {status}"
        log.email_content = message
        log.for_user = user
        log.type = "Alert"
        log.document_type = "HD Ticket"
        log.document_name = ticket_id
        log.insert(ignore_permissions=True)
    except Exception:
        pass  # Notification log failure must never block the caller


def _expiry_email_body(plan_name: str, plan_type: str, expiry_date, days: int) -> str:
    portal_url = frappe.utils.get_url("/services")
    return f"""
        <p>Dear customer,</p>
        <p>Your <strong>{plan_type}</strong> <strong>{plan_name}</strong>
        will expire on <strong>{expiry_date}</strong> ({days} days from now).</p>
        <p>Please log in to your
        <a href="{portal_url}">WorkDesk</a> to renew.</p>
        <p>If you need help, open a support ticket and our team will assist you.</p>
    """
