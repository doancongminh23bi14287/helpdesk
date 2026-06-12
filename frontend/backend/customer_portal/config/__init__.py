"""
customer_portal/config/__init__.py
Central configuration constants for the customer portal.
"""

# ── Ticket priorities ──────────────────────────────────────────────────────────
DEFAULT_TICKET_PRIORITY = "Medium"
TICKET_PRIORITIES = ["Low", "Medium", "High", "Urgent"]

# ── Ticket type ────────────────────────────────────────────────────────────────
DEFAULT_TICKET_TYPE = "Question"

# ── Ticket statuses ────────────────────────────────────────────────────────────
OPEN_TICKET_STATUSES = ["Open", "Pending", "Replied"]
CLOSED_TICKET_STATUSES = ["Resolved", "Closed"]

# ── DocType names ──────────────────────────────────────────────────────────────
# Detect whether Frappe Helpdesk ("HD Ticket") is installed at import time.
# Falls back to ERPNext core "Issue" doctype if Helpdesk is not present.
def _resolve_ticket_doctype() -> str:
    try:
        import frappe
        if frappe.db and frappe.db.exists("DocType", "HD Ticket"):
            return "HD Ticket"
    except Exception:
        pass
    return "Issue"


HELPDESK_TICKET_DOCTYPE: str = _resolve_ticket_doctype()
TICKET_DOCTYPES = ["HD Ticket", "Issue"]

# ERPNext doctype used to represent a customer's active service instance.
SERVICE_INSTANCE_DOCTYPE = "Subscription"

# ── Access control ─────────────────────────────────────────────────────────────
PORTAL_USER_ROLE = "Customer"

# ── Ticket type → Team mapping ─────────────────────────────────────────────────
# Keys must match exactly the HD Ticket Type names in Frappe Helpdesk.
# Values must match exactly the HD Team names.
# Teams that don't exist in the system are silently skipped (best-effort).
SERVICE_TEAM_MAP: dict[str, str] = {
    "Technical Support": "IT Team",
    "Billing":           "Finance Team",
    "General Inquiry":   "Customer Service",
    "Account":           "Customer Service",
    "Bug Report":        "IT Team",
    "Feature Request":   "IT Team",
}

# Priority label translations (used by get_ticket_priorities endpoint)
PRIORITY_LABELS: list[dict] = [
    {"value": "Low",    "label": "Thấp"},
    {"value": "Medium", "label": "Trung bình"},
    {"value": "High",   "label": "Cao"},
    {"value": "Urgent", "label": "Khẩn cấp"},
]
