"""
Ticket API controllers — thin layer between HTTP and ticket_service.
No business logic here. Validate input → call service → return result.
"""
import frappe
from frappe import _

from customer_portal.config import DEFAULT_TICKET_PRIORITY, PRIORITY_LABELS
from customer_portal.models.ticket import TicketPriority
from customer_portal.services import ticket_service


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_auth():
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)


def _is_staff(user: str) -> bool:
    """True if the user holds a Helpdesk Agent or System Manager role."""
    roles = frappe.get_roles(user)
    return bool({"Helpdesk Agent", "System Manager"} & set(roles))


def _require(name: str, value):
    if not value or (isinstance(value, str) and not value.strip()):
        frappe.throw(_("{0} is required.").format(name))


# ── Category / priority metadata endpoints ────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def get_service_categories():
    """Return HD Ticket Types from Helpdesk, ordered alphabetically."""
    return frappe.get_all(
        "HD Ticket Type",
        fields=["name"],
        order_by="name asc",
    )


@frappe.whitelist(allow_guest=False)
def get_ticket_priorities():
    """Return priority options with Vietnamese labels."""
    return PRIORITY_LABELS


# ── Ticket endpoints ──────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def get_my_tickets():
    """GET /api/method/customer_portal.api.tickets.get_my_tickets"""
    _require_auth()
    return ticket_service.get_my_tickets(frappe.session.user)


@frappe.whitelist(allow_guest=False)
def get_ticket_detail(ticket_id: str):
    """GET /api/method/customer_portal.api.tickets.get_ticket_detail?ticket_id=HD-0001"""
    _require_auth()
    _require("ticket_id", ticket_id)
    user = frappe.session.user
    ticket, messages = ticket_service.get_ticket_detail(
        ticket_id=ticket_id,
        user_email=user,
        is_staff=_is_staff(user),
    )
    return {"ticket": ticket.as_dict(), "messages": messages}


_VALID_TICKET_TYPES = ["Bug", "Incident", "Question", "Unspecified"]
_DEFAULT_TICKET_TYPE = "Question"


@frappe.whitelist(allow_guest=False)
def create_ticket(
    subject: str,
    description: str,
    priority: str = DEFAULT_TICKET_PRIORITY,
    ticket_type: str = None,
    service_id: str = None,
):
    """POST /api/method/customer_portal.api.tickets.create_ticket"""
    _require_auth()
    _require("subject", subject)
    _require("description", description)

    if ticket_type not in _VALID_TICKET_TYPES:
        ticket_type = _DEFAULT_TICKET_TYPE

    ticket = ticket_service.create_ticket(
        subject=subject,
        description=description,
        priority=priority or TicketPriority.DEFAULT,
        user_email=frappe.session.user,
        ticket_type=ticket_type,
        service_id=service_id or None,
    )
    return ticket.as_dict()


@frappe.whitelist(allow_guest=False)
def reply_to_ticket(ticket_id: str, message: str):
    """POST /api/method/customer_portal.api.tickets.reply_to_ticket"""
    _require_auth()
    _require("ticket_id", ticket_id)
    _require("message", message)

    user = frappe.session.user
    comment = ticket_service.reply_to_ticket(
        ticket_id=ticket_id,
        content=message,
        user_email=user,
        is_staff=_is_staff(user),
    )
    return comment.as_dict()


@frappe.whitelist(allow_guest=False)
def get_portal_summary():
    """GET /api/method/customer_portal.api.tickets.get_portal_summary"""
    _require_auth()
    return ticket_service.get_portal_summary(frappe.session.user)
