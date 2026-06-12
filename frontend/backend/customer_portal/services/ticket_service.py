"""
Ticket service — all business logic for tickets and messages.
Controllers must NOT contain business logic; they call this layer.
Repositories must NOT contain business logic; they are called by this layer.
"""
import frappe
from frappe import _

from customer_portal.models.ticket import TicketStatus, TicketPriority, MessageType
from customer_portal.repositories import (
    ticket_repository,
    message_repository,
)
from customer_portal.services import notification_service, sla_service


# ── Queries ───────────────────────────────────────────────────────────────────

def get_my_tickets(user_email: str) -> list:
    """Return ticket list for the portal user (no sensitive fields)."""
    return ticket_repository.get_tickets_for_user(user_email)


def get_ticket_detail(ticket_id: str, user_email: str, is_staff: bool = False):
    """
    Return (ticket, messages) for a ticket detail view.
    Staff can access any ticket; customers can only view their own.
    Staff see all message types; customers only see public replies.
    """
    if is_staff:
        ticket = ticket_repository.get_ticket(ticket_id)
        messages = message_repository.get_messages(ticket_id)
    else:
        ticket = ticket_repository.get_ticket_owned_by(ticket_id, user_email)
        messages = message_repository.get_public_messages(ticket_id)

    return ticket, messages


def get_portal_summary(user_email: str) -> dict:
    """
    Aggregate dashboard data in a single call.
    Uses raw SQL (get_status_counts) so portal users always see their own
    tickets regardless of HD Ticket role permissions.
    Open = any status not in {Resolved, Closed} (includes Open, Pending, Replied).

    services_count and total_orders return 0 when no Customer record is linked
    to the user (AuthenticationError). Any other exception is logged and re-raised.
    """
    from customer_portal.config import CLOSED_TICKET_STATUSES
    from customer_portal.repositories import service_repository, sales_order_repository
    from customer_portal.repositories.customer_repository import get_customer_for_user

    counts = ticket_repository.get_status_counts(user_email)
    total  = sum(counts.values())

    closed_set       = set(CLOSED_TICKET_STATUSES)
    open_tickets     = sum(cnt for status, cnt in counts.items() if status not in closed_set)
    resolved_tickets = sum(cnt for status, cnt in counts.items() if status in closed_set)

    services_count = 0
    total_orders   = 0
    try:
        customer = get_customer_for_user(user_email)
        hosting = service_repository.get_hosting_plans(customer)
        subs    = service_repository.get_subscriptions(customer)
        services_count = len(hosting) + len(subs)
        total_orders   = len(sales_order_repository.get_orders_for_customer(customer))
    except frappe.AuthenticationError:
        pass
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_portal_summary error")
        raise

    return {
        "ticket_counts":    counts,
        "total_tickets":    total,
        "open_tickets":     open_tickets,
        "resolved_tickets": resolved_tickets,
        "services_count":   services_count,
        "total_orders":     total_orders,
    }


# ── Mutations ─────────────────────────────────────────────────────────────────

def create_ticket(
    *,
    subject: str,
    description: str,
    priority: str,
    user_email: str,
    ticket_type: str | None = None,
    service_id: str | None = None,
) -> object:
    """
    Validate input, create the HD Ticket, and optionally apply SLA.
    Returns the saved document.
    """
    _validate_priority(priority)

    ticket = ticket_repository.create_ticket(
        subject=subject.strip()[:140],
        description=description.strip(),
        priority=priority,
        user_email=user_email,
        ticket_type=ticket_type,
        service_id=service_id,
    )

    if service_id:
        sla_service.apply_sla(ticket, service_id)

    return ticket


def reply_to_ticket(
    *,
    ticket_id: str,
    content: str,
    user_email: str,
    is_staff: bool = False,
) -> object:
    """
    Append a reply to a ticket thread.

    Rules:
    - Customers: can only reply to their own non-terminal tickets; posting reopens resolved ones.
    - Staff: can post to any ticket and may choose internal_note type (via is_staff flag).
    """
    if is_staff:
        ticket = ticket_repository.get_ticket(ticket_id)
        message_type = MessageType.PUBLIC_REPLY  # staff UI can override this at API layer
    else:
        ticket = ticket_repository.get_ticket_owned_by(ticket_id, user_email)
        if ticket.status in TicketStatus.TERMINAL:
            frappe.throw(
                _("Ticket {0} is {1} and no longer accepts replies.").format(ticket_id, ticket.status)
            )
        message_type = MessageType.PUBLIC_REPLY

    comment = message_repository.create_message(
        ticket_id=ticket_id,
        content=content.strip(),
        author=user_email,
        message_type=message_type,
    )

    # Customer reply on a resolved/replied ticket → reopen
    if not is_staff and ticket.status in TicketStatus.REOPEN_ON_REPLY:
        ticket_repository.update_ticket_status(ticket, TicketStatus.OPEN)

    # Notify customer when staff posts a public reply
    if is_staff and message_type == MessageType.PUBLIC_REPLY:
        notification_service.notify_agent_reply(ticket, comment)

    return comment


# ── Private ───────────────────────────────────────────────────────────────────

def _validate_priority(priority: str):
    if priority not in TicketPriority.ALL:
        frappe.throw(_("Invalid priority '{0}'. Allowed: {1}").format(priority, ", ".join(TicketPriority.ALL)))
