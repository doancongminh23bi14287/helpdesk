"""
Services API controllers — thin layer for customer services endpoints.
"""
import frappe
from frappe import _
from customer_portal.services import customer_service


def _require_auth():
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)


@frappe.whitelist()
def get_customer_services():
    """GET /api/method/customer_portal.api.services.get_customer_services"""
    _require_auth()
    return customer_service.get_services_for_user(frappe.session.user)
