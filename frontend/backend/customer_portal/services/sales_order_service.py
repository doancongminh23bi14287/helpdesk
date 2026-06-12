"""
Sales Order service — business logic for resolving orders for portal users.
"""
from customer_portal.repositories.customer_repository import get_customer_for_user
from customer_portal.repositories import sales_order_repository


def get_sales_orders_for_user(user_email: str) -> dict:
    """Resolve user → customer → sales orders list."""
    customer = get_customer_for_user(user_email)
    orders = sales_order_repository.get_orders_for_customer(customer)
    return {
        "customer": customer,
        "orders": [
            {
                "name": o.name,
                "status": o.status,
                "transaction_date": str(o.transaction_date) if o.transaction_date else None,
                "delivery_date": str(o.delivery_date) if o.delivery_date else None,
                "grand_total": float(o.grand_total or 0),
                "total_qty": float(o.total_qty or 0),
                "currency": o.currency,
            }
            for o in orders
        ],
    }


def get_order_detail_for_user(user_email: str, order_id: str) -> dict:
    """Resolve user → customer → single order with items (ownership-checked)."""
    customer = get_customer_for_user(user_email)
    return sales_order_repository.get_order_detail_by_customer(order_id, customer)
