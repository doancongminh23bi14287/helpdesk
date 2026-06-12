"""
customer_portal/api/auth.py
Authentication endpoints for the customer portal.
"""

import frappe


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_customer_name(email: str) -> str | None:
    """
    Resolve the ERPNext Customer linked to this user email.
    Checks Contact → Customer link first, then falls back to Customer.email_id.
    """
    contact_name = frappe.db.get_value("Contact", {"user": email}, "name")
    if contact_name:
        customer_link = frappe.db.get_value(
            "Dynamic Link",
            {"parent": contact_name, "link_doctype": "Customer"},
            "link_name",
        )
        if customer_link:
            return customer_link

    return frappe.db.get_value("Customer", {"email_id": email}, "name")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def whoami():
    """
    Return the current session's user, roles, and linked Customer name.
    Guest sessions return user=None so the frontend can redirect to login.
    """
    user = frappe.session.user
    if not user or user == "Guest":
        return {"user": None, "roles": [], "customer": None}

    customer = _get_customer_name(user)
    return {
        "user": user,
        "roles": frappe.get_roles(user),
        "customer": customer,
    }


@frappe.whitelist(allow_guest=True)
def register_user(first_name, last_name, email, password, mobile_no=""):
    if frappe.db.exists("User", email):
        frappe.throw("Email already registered")

    user_doc = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "mobile_no": mobile_no,
        "new_password": password,
        "user_type": "Website User",
        "send_welcome_email": 0,
    })
    user_doc.append("roles", {"role": "Customer"})
    user_doc.insert(ignore_permissions=True)

    full_name = f"{first_name} {last_name}".strip()
    customer_doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": full_name,
        "customer_group": "All Customer Groups",
        "territory": "All Territories",
        "email_id": email,
    })
    customer_doc.insert(ignore_permissions=True)

    _create_contact(full_name, email, "", mobile_no, customer_doc.name)
    frappe.db.commit()
    return {"message": "Registration successful"}


def _create_contact(full_name, email, user_image, mobile_no, customer_name):
    """Create a Contact linked to the Customer so customer_repository can resolve it."""
    try:
        contact = frappe.new_doc("Contact")
        contact.first_name = full_name
        contact.email_id = email
        contact.user = email
        if user_image:
            contact.image = user_image
        if mobile_no:
            contact.mobile_no = mobile_no
        contact.append("email_ids", {"email_id": email, "is_primary": 1})
        contact.append("links", {"link_doctype": "Customer", "link_name": customer_name})
        contact.insert(ignore_permissions=True)
    except Exception:
        # Contact creation is best-effort; the Customer with email_id is the primary fallback.
        frappe.log_error(
            title="customer_portal: _create_contact failed",
            message=frappe.get_traceback(),
        )
