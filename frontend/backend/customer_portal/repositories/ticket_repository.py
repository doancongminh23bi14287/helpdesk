"""
Ticket repository — raw DB access for HD Ticket documents.
No business logic here; only query and persistence primitives.
"""
import frappe
from frappe import _

_TICKET_LIST_FIELDS = [
    "name", "subject", "status", "priority", "ticket_type",
    "creation", "modified", "raised_by", "service_id",
    "sla_response_deadline", "sla_resolution_deadline",
]

_TICKET_DETAIL_FIELDS = _TICKET_LIST_FIELDS + ["description", "via_customer_portal", "team", "customer"]


def get_tickets_for_user(user_email: str, limit: int = 100) -> list:
    """
    Fetch all tickets raised by a user, latest-modified first.
    ignore_permissions=True is safe: ownership is already enforced by
    the raised_by filter. Without it, portal users (Customer role) get
    an empty list because HD Ticket requires HD Agent/System Manager for reads.
    """
    return frappe.get_all(
        "HD Ticket",
        filters={"raised_by": user_email},
        fields=_TICKET_LIST_FIELDS,
        order_by="modified desc",
        limit=limit,
        ignore_permissions=True,
    )


def get_ticket(ticket_id: str):
    """
    Fetch a single HD Ticket document.
    ignore_permissions=True for the same reason as get_tickets_for_user —
    portal users lack role-level read on HD Ticket; ownership is checked separately.
    """
    return frappe.get_doc("HD Ticket", ticket_id, ignore_permissions=True)


def get_ticket_owned_by(ticket_id: str, user_email: str):
    """
    Fetch a ticket and assert the caller is its owner.
    Raises PermissionError for foreign tickets to avoid information disclosure.
    """
    ticket = get_ticket(ticket_id)
    if ticket.raised_by != user_email:
        frappe.throw(_("You do not have access to ticket {0}.").format(ticket_id), frappe.PermissionError)
    return ticket


def create_ticket(
    *,
    subject: str,
    description: str,
    priority: str,
    user_email: str,
    ticket_type: str | None = None,
    service_id: str | None = None,
):
    """Insert a new HD Ticket and return the saved document."""
    from customer_portal.config import SERVICE_TEAM_MAP

    doc = frappe.new_doc("HD Ticket")
    doc.subject = subject
    doc.description = description
    doc.priority = priority
    doc.raised_by = user_email
    doc.via_customer_portal = 1

    if service_id:
        doc.service_id = service_id

    # Set ticket type and auto-derive team from SERVICE_TEAM_MAP
    if ticket_type:
        try:
            doc.ticket_type = ticket_type
        except Exception:
            pass
        team = SERVICE_TEAM_MAP.get(ticket_type)
        if team:
            try:
                doc.team = team
            except Exception:
                pass

    # Auto-link Customer from the logged-in user's email
    try:
        from customer_portal.repositories.customer_repository import get_customer_for_user
        customer = get_customer_for_user(user_email)
        if customer:
            doc.customer = customer
    except Exception:
        pass

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


def get_status_counts(user_email: str) -> dict:
    """
    Return {status: count} merged across HD Ticket (Frappe Helpdesk)
    and Issue (ERPNext standard). Either doctype may be absent on a given
    site; missing tables are tolerated so the other still contributes.
    """
    counts: dict = {}
    for doctype in ("HD Ticket", "Issue"):
        try:
            rows = frappe.db.sql(
                f"""
                SELECT status, COUNT(*) AS cnt
                FROM `tab{doctype}`
                WHERE raised_by = %s
                GROUP BY status
                """,
                user_email,
                as_dict=True,
            )
        except Exception:
            continue
        for r in rows:
            counts[r.status] = counts.get(r.status, 0) + r.cnt
    return counts


def update_ticket_status(ticket, new_status: str):
    """Persist a status change on an already-loaded ticket document."""
    ticket.status = new_status
    ticket.save(ignore_permissions=True)
    frappe.db.commit()
