"""
Sales Order repository — DB queries using Frappe ORM.
Preferred over outbound HTTP for same-bench deployments.
"""
import frappe
from frappe import _

_LIST_FIELDS = [
    "name", "status", "transaction_date", "delivery_date",
    "grand_total", "currency", "total_qty", "customer",
]


def get_orders_for_customer(customer: str, limit: int = 50) -> list:
    """Fetch non-cancelled Sales Orders for a customer, newest first."""
    return frappe.get_all(
        "Sales Order",
        filters={"customer": customer, "docstatus": ("!=", 2)},
        fields=_LIST_FIELDS,
        order_by="transaction_date desc",
        limit=limit,
    )


def get_order_detail_by_customer(order_id: str, customer: str) -> dict:
    """Return a Sales Order with full line items, asserting customer ownership."""
    doc = frappe.get_doc("Sales Order", order_id)
    if doc.customer != customer:
        frappe.throw(
            _("You do not have access to order {0}.").format(order_id),
            frappe.PermissionError,
        )
    return {
        "name": doc.name,
        "status": doc.status,
        "transaction_date": str(doc.transaction_date) if doc.transaction_date else None,
        "delivery_date": str(doc.delivery_date) if doc.delivery_date else None,
        "grand_total": float(doc.grand_total or 0),
        "total_qty": float(doc.total_qty or 0),
        "currency": doc.currency,
        "customer": doc.customer,
        "customer_name": doc.customer_name,
        "items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": float(item.qty or 0),
                "uom": item.uom,
                "rate": float(item.rate or 0),
                "amount": float(item.amount or 0),
            }
            for item in (doc.items or [])
        ],
    }
