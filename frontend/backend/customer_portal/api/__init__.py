"""
customer_portal/api/__init__.py
Backward-compatible shim — all endpoints delegate to layered sub-modules.

Each import block is isolated in its own try/except so a single broken
sub-module (e.g. a missing DocType during bench install) does not prevent
the other endpoints from loading. Without this, one ImportError anywhere
in the chain causes Frappe to report the entire package as unavailable.

NOTE: login and logout intentionally use Frappe's built-in endpoints
(/api/method/login, /api/method/logout) and are NOT re-exported here.
"""

import sys
import traceback


def _log_api_import_error(module_name: str, exc: BaseException) -> None:
    print(f"customer_portal.api: failed to import {module_name}: {exc}", file=sys.stderr)
    traceback.print_exc()


try:
    from customer_portal.api.tickets import (   # noqa: F401
        get_my_tickets,
        create_ticket,
        reply_to_ticket,
        get_portal_summary,
        get_service_categories,
        get_ticket_priorities,
    )
except Exception as exc:
    _log_api_import_error("customer_portal.api.tickets", exc)

try:
    from customer_portal.api.services import (  # noqa: F401
        get_customer_services,
    )
except Exception as exc:
    _log_api_import_error("customer_portal.api.services", exc)

try:
    from customer_portal.api.auth import (      # noqa: F401
        whoami,
        register_user,
    )
except Exception as exc:
    _log_api_import_error("customer_portal.api.auth", exc)

try:
    from customer_portal.api.sales_orders import (  # noqa: F401
        get_my_sales_orders,
        get_order_details,
    )
except Exception as exc:
    _log_api_import_error("customer_portal.api.sales_orders", exc)
