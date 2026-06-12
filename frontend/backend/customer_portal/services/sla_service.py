"""
SLA service — computes and applies response/resolution deadlines to tickets.
SLA rules live in the 'SLA Policy' DocType (linked via Customer Service),
so changing SLA requirements never requires touching ticket code.
"""
from datetime import datetime, timedelta
import frappe


def apply_sla(ticket, service_id: str):
    """
    Apply SLA deadlines to a freshly created ticket.
    Looks up: ticket.priority → SLA Policy → response/resolution hours.
    Silently skips if the service or SLA is not configured.
    """
    try:
        service = frappe.get_doc("Customer Service", service_id)
        if not service.get("sla_policy"):
            return

        sla = frappe.get_doc("SLA Policy", service.sla_policy)
        rule = _find_priority_rule(sla, ticket.priority)
        if not rule:
            return

        now = datetime.now()
        ticket.sla_response_deadline = now + timedelta(hours=rule.response_time_hours)
        ticket.sla_resolution_deadline = now + timedelta(hours=rule.resolution_time_hours)
        ticket.save(ignore_permissions=True)
        frappe.db.commit()

    except frappe.DoesNotExistError:
        pass  # Service or SLA Policy not found — skip gracefully
    except Exception as exc:
        frappe.log_error(str(exc), "SLA Apply Error")


def is_breached(ticket) -> bool:
    """Return True if the ticket has exceeded its resolution SLA deadline."""
    deadline = ticket.get("sla_resolution_deadline")
    if not deadline:
        return False
    return frappe.utils.now_datetime() > deadline


def time_remaining(ticket) -> int | None:
    """Return minutes remaining before SLA breach, or None if no SLA set."""
    deadline = ticket.get("sla_resolution_deadline")
    if not deadline:
        return None
    delta = deadline - frappe.utils.now_datetime()
    return max(0, int(delta.total_seconds() / 60))


# ── Private ───────────────────────────────────────────────────────────────────

def _find_priority_rule(sla_doc, priority: str):
    """Find the SLA row matching the ticket priority."""
    for row in sla_doc.get("priorities", []):
        if row.priority == priority:
            return row
    return None
