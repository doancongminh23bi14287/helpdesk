"""
customer_portal/hooks/ticket_hooks.py
Doc-event hooks for HD Ticket.

Business logic has been moved to notification_service; this file is now
a thin dispatcher that satisfies the Frappe hook registration contract.
"""
from customer_portal.services.notification_service import notify_ticket_status_change


def on_ticket_update(doc, method=None):
    """
    Triggered on every HD Ticket save via hooks.py → doc_events.
    Delegates entirely to the notification service.
    """
    notify_ticket_status_change(doc, doc.status)
