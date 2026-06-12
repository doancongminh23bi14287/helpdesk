"""
Sales Order API controller.
Endpoint: /api/method/customer_portal.api.sales_orders.get_my_sales_orders
"""
import frappe
from frappe import _
from customer_portal.services import sales_order_service


def _require_auth():
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)


@frappe.whitelist()
def get_my_sales_orders():
    """Return sales orders for the currently logged-in customer."""
    _require_auth()
    return sales_order_service.get_sales_orders_for_user(frappe.session.user)


@frappe.whitelist()
def get_order_details(order_id: str):
    """
    Return a single Sales Order with full line items.
    GET /api/method/customer_portal.api.sales_orders.get_order_details?order_id=SO-0001
    """
    _require_auth()
    if not order_id:
        frappe.throw(_("order_id is required."), frappe.ValidationError)
    return sales_order_service.get_order_detail_for_user(frappe.session.user, order_id)
