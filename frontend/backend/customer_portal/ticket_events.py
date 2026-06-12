"""
customer_portal/ticket_events.py
Doc-event dispatcher for HD Ticket.

Placed at the package root (NOT inside hooks/) to avoid the Python name
conflict where hooks.py (a file) shadows the hooks/ directory, making
`customer_portal.hooks.ticket_hooks` unresolvable as "not a package".
"""
from customer_portal.services.notification_service import notify_ticket_status_change


def on_ticket_update(doc, method=None):
    notify_ticket_status_change(doc, doc.status)
