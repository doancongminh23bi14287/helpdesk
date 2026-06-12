"""
Customer repository — all DB lookups for resolving a portal user → Customer.
Isolated here so the resolution strategy can change without touching business logic.
"""
import frappe
from frappe import _


def get_customer_for_user(user_email: str) -> str:
    """
    Resolve the ERPNext Customer name linked to a portal user email.
    Resolution order:
      1. Contact.user == user_email → Dynamic Link → Customer
      2. Contact.email_id == user_email → Dynamic Link → Customer
      3. Customer.email_id == user_email (direct match)
    Raises AuthenticationError if no customer is found.
    """
    # Path 1: Contact linked via Frappe user account
    contact_name = frappe.db.get_value("Contact", {"user": user_email}, "name")
    if contact_name:
        customer = _customer_from_contact(contact_name)
        if customer:
            return customer

    # Path 2: Contact matched by email_id
    contact_name = frappe.db.get_value("Contact", {"email_id": user_email}, "name")
    if contact_name:
        customer = _customer_from_contact(contact_name)
        if customer:
            return customer

    # Path 3: Customer.email_id direct match
    customer = frappe.db.get_value("Customer", {"email_id": user_email}, "name")
    if customer:
        return customer

    frappe.throw(
        _("No customer account is linked to {0}. Please contact support.").format(user_email),
        frappe.AuthenticationError,
    )


def get_customer_email(customer_name: str) -> str | None:
    """
    Return the primary email for a Customer — used for outbound notifications.
    Falls back to the first linked Contact email.
    """
    email = frappe.db.get_value("Customer", customer_name, "email_id")
    if email:
        return email

    # Fallback: first Contact linked to this customer
    contact_name = frappe.db.get_value(
        "Dynamic Link",
        {
            "link_doctype": "Customer",
            "link_name": customer_name,
            "parenttype": "Contact",
        },
        "parent",
    )
    if contact_name:
        return frappe.db.get_value("Contact", contact_name, "email_id")

    return None


# ── Private ──────────────────────────────────────────────────────────────────

def _customer_from_contact(contact_name: str) -> str | None:
    return frappe.db.get_value(
        "Dynamic Link",
        {
            "parenttype": "Contact",
            "parent": contact_name,
            "link_doctype": "Customer",
        },
        "link_name",
    )
