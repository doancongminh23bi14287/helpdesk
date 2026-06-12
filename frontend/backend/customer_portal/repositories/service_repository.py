"""
Service repository — DB access for Hosting Plans and ERPNext Subscriptions.
"""
import json
import frappe


def get_hosting_plans(customer: str) -> list:
    """Fetch Hosting Plans linked to a customer. Returns [] if DocType absent."""
    if not frappe.db.exists("DocType", "Hosting Plan"):
        return []

    return frappe.get_all(
        "Hosting Plan",
        filters={"customer": customer, "status": ("!=", "Deleted")},
        fields=["name", "plan", "domain", "status", "expiry_date", "disk_usage", "monthly_cost"],
        order_by="expiry_date asc",
    )


def get_subscriptions(customer: str) -> list:
    """Fetch ERPNext Subscriptions for a customer and normalise the plans field."""
    subs = frappe.get_all(
        "Subscription",
        filters={"party_type": "Customer", "party": customer},
        fields=["name", "party", "status", "current_invoice_start", "current_invoice_end", "plans"],
        order_by="current_invoice_end asc",
    )
    for sub in subs:
        # ERPNext may return plans as a JSON string in older versions
        if isinstance(sub.plans, str):
            try:
                sub.plans = json.loads(sub.plans)
            except (json.JSONDecodeError, TypeError):
                sub.plans = []
    return subs


def get_hosting_plans_expiring_on(target_date: str, status: str = "Active") -> list:
    """Return hosting plans whose expiry_date matches target_date exactly."""
    if not frappe.db.exists("DocType", "Hosting Plan"):
        return []

    return frappe.get_all(
        "Hosting Plan",
        filters={"status": status, "expiry_date": target_date},
        fields=["name", "customer", "plan", "expiry_date"],
    )
