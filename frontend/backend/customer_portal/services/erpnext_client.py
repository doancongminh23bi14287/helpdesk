"""
ERPNext REST client for authenticated server-to-server HTTP calls.

Credentials are loaded exclusively from Frappe site config (site_config.json).
Never pass credentials from the frontend or environment variables that could
appear in browser network requests or client-side logs.

Required site_config.json keys for the running Frappe site:
    "erpnext_api_key": "your_key_here",
    "erpnext_api_secret": "your_secret_here",
    "erpnext_url": "http://erpnext.localhost"   # omit if same site

Usage:
    from customer_portal.services.erpnext_client import get_client
    client = get_client()
    ok = client.test_connection()
"""
import frappe
import requests
from requests.exceptions import RequestException


class ERPNextAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"ERPNext {status_code}: {message}")


class ERPNextClient:

    def __init__(self):
        conf = frappe.conf
        api_key = conf.get("erpnext_api_key", "")
        api_secret = conf.get("erpnext_api_secret", "")
        # Default to same Frappe site if no separate URL is configured
        self._base_url = conf.get("erpnext_url", frappe.utils.get_url()).rstrip("/")
        # Frappe requires exactly: "token KEY:SECRET" — no extra whitespace.
        # Suppress the Expect: 100-continue header that some versions of
        # the requests library add for non-trivial request bodies.
        # Nginx/Frappe returns 417 Expectation Failed when it receives
        # Expect: 100-continue and is not configured to handle it.
        self._base_headers = {
            "Authorization": f"token {api_key}:{api_secret}",
            "Expect": "",
        }
        self._json_headers = {
            **self._base_headers,
            "Content-Type": "application/json",
        }

    def get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.get(url, headers=self._base_headers, params=params, timeout=10)
        except RequestException as exc:
            frappe.log_error(str(exc), "ERPNextClient GET network error")
            raise ERPNextAPIError(0, str(exc)) from exc
        return self._parse(resp)

    def post(self, endpoint: str, data: dict = None) -> dict:
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.post(url, headers=self._json_headers, json=data or {}, timeout=10)
        except RequestException as exc:
            frappe.log_error(str(exc), "ERPNextClient POST network error")
            raise ERPNextAPIError(0, str(exc)) from exc
        return self._parse(resp)

    def put(self, endpoint: str, data: dict = None) -> dict:
        """PUT {base_url}/{endpoint} with JSON body — used for document updates."""
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.put(url, headers=self._json_headers, json=data or {}, timeout=10)
        except RequestException as exc:
            frappe.log_error(str(exc), "ERPNextClient PUT network error")
            raise ERPNextAPIError(0, str(exc)) from exc
        return self._parse(resp)

    def _parse(self, resp: requests.Response) -> dict:
        if resp.status_code == 401:
            raise ERPNextAPIError(401, "Invalid API credentials — check erpnext_api_key/secret in site_config.json")
        if resp.status_code == 403:
            raise ERPNextAPIError(403, "API user lacks permission — check ERPNext role assignments")
        if resp.status_code == 404:
            raise ERPNextAPIError(404, "Endpoint not found")
        if not resp.ok:
            try:
                msg = resp.json().get("exception") or resp.json().get("message") or resp.text
            except Exception:
                msg = resp.text
            raise ERPNextAPIError(resp.status_code, msg)
        return resp.json()

    def test_connection(self) -> bool:
        """Validate credentials via frappe.auth.get_logged_user. Returns True on success."""
        try:
            result = self.get("/api/method/frappe.auth.get_logged_user")
            user = result.get("message")
            frappe.logger().info(f"ERPNextClient connected as: {user}")
            return True
        except ERPNextAPIError as exc:
            frappe.log_error(str(exc), "ERPNextClient connection test failed")
            return False

    def get_customer_details(self, email: str) -> dict | None:
        result = self.get("/api/resource/Customer", params={
            "filters": f'[["email_id","=","{email}"]]',
            "fields": '["name","customer_name","email_id","mobile_no","customer_group"]',
            "limit": 1,
        })
        data = result.get("data") or []
        return data[0] if data else None

    def get_sales_orders(self, customer_id: str) -> list:
        result = self.get("/api/resource/Sales Order", params={
            "filters": f'[["customer","=","{customer_id}"],["docstatus","!=",2]]',
            "fields": '["name","status","transaction_date","delivery_date","grand_total","currency"]',
            "order_by": "transaction_date desc",
            "limit": 50,
        })
        return result.get("data") or []

    def get_tickets(self, customer_id: str) -> list:
        result = self.get("/api/resource/HD Ticket", params={
            "filters": f'[["customer","=","{customer_id}"]]',
            "fields": '["name","subject","status","priority","creation","modified","raised_by"]',
            "order_by": "modified desc",
            "limit": 100,
        })
        return result.get("data") or []

    def create_ticket(self, subject: str, description: str, raised_by: str) -> dict:
        result = self.post("/api/resource/HD Ticket", data={
            "subject": subject,
            "description": description,
            "raised_by": raised_by,
            "via_customer_portal": 1,
        })
        return result.get("data") or {}

    # ── Extended domain methods ───────────────────────────────────────────────

    def get_customer_orders(self, customer_id: str) -> list:
        """Fetch Sales Orders with extended fields including total_qty."""
        result = self.get("/api/resource/Sales Order", params={
            "filters": f'[["customer","=","{customer_id}"],["docstatus","!=",2]]',
            "fields": '["name","status","transaction_date","delivery_date","grand_total","currency","total_qty"]',
            "order_by": "transaction_date desc",
            "limit": 50,
        })
        return result.get("data") or []

    def get_order_details(self, order_id: str) -> dict | None:
        """Fetch a single Sales Order document with full line items."""
        try:
            result = self.get(f"/api/resource/Sales Order/{order_id}")
            return result.get("data")
        except ERPNextAPIError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_customer_tickets(self, customer_email: str) -> list:
        """
        Fetch tickets for the given email.
        Tries HD Ticket (Frappe Helpdesk) first, then falls back to Issue (ERPNext standard).
        """
        for doctype, filter_field in (("HD Ticket", "raised_by"), ("Issue", "raised_by")):
            try:
                result = self.get(f"/api/resource/{doctype}", params={
                    "filters": f'[["{filter_field}","=","{customer_email}"]]',
                    "fields": '["name","subject","status","priority","creation","modified"]',
                    "order_by": "modified desc",
                    "limit": 100,
                })
                return result.get("data") or []
            except ERPNextAPIError as exc:
                if exc.status_code in (403, 404):
                    continue
                raise
        return []

    def create_new_ticket(
        self, subject: str, description: str, raised_by: str, priority: str = "Medium"
    ) -> dict:
        """
        Create a support ticket with priority.
        Tries HD Ticket first, falls back to Issue.
        priority values: Low | Medium | High | Urgent
        """
        attempts = (
            ("HD Ticket", {
                "subject": subject, "description": description,
                "raised_by": raised_by, "priority": priority, "via_customer_portal": 1,
            }),
            ("Issue", {
                "subject": subject, "description": description,
                "raised_by": raised_by, "priority": priority,
            }),
        )
        for doctype, payload in attempts:
            try:
                result = self.post(f"/api/resource/{doctype}", data=payload)
                return result.get("data") or {}
            except ERPNextAPIError as exc:
                if exc.status_code in (403, 404):
                    continue
                raise
        frappe.throw("Could not create ticket — check Helpdesk permissions.", frappe.ValidationError)

    def update_customer_profile(self, customer_id: str, data: dict) -> dict:
        """
        Update allowed Customer fields (mobile_no, email_id, customer_name, address).
        Keys not in the allowlist are silently dropped.
        """
        _UPDATABLE = {"mobile_no", "email_id", "customer_name", "customer_primary_address"}
        filtered = {k: v for k, v in data.items() if k in _UPDATABLE}
        if not filtered:
            frappe.throw("No valid fields to update.", frappe.ValidationError)
        result = self.put(f"/api/resource/Customer/{customer_id}", data=filtered)
        return result.get("data") or {}

    def get_dashboard_stats(self, customer_id: str) -> dict:
        """
        Return aggregated portal stats via outbound HTTP calls to ERPNext.
        Returns: {"open_tickets": int, "closed_tickets": int, "total_orders": int}

        HD Tickets are filtered by raised_by (email) — the portal sets that field,
        not the Customer link — so we resolve the email first from Customer.
        Individual call errors are logged and swallowed to return a partial result.
        """
        customer_email = None
        try:
            cust = self.get(f"/api/resource/Customer/{customer_id}")
            customer_email = (cust.get("data") or {}).get("email_id")
        except ERPNextAPIError:
            pass

        open_count = closed_count = 0

        if customer_email:
            for doctype in ("HD Ticket", "Issue"):
                try:
                    open_r = self.get(f"/api/resource/{doctype}", params={
                        "filters": f'[["raised_by","=","{customer_email}"],["status","in","Open,Replied"]]',
                        "fields": '["name"]',
                        "limit": 500,
                    })
                    open_count = len(open_r.get("data") or [])

                    closed_r = self.get(f"/api/resource/{doctype}", params={
                        "filters": f'[["raised_by","=","{customer_email}"],["status","in","Resolved,Closed"]]',
                        "fields": '["name"]',
                        "limit": 500,
                    })
                    closed_count = len(closed_r.get("data") or [])
                    break
                except ERPNextAPIError as exc:
                    if exc.status_code in (403, 404):
                        continue
                    frappe.log_error(str(exc), "get_dashboard_stats ticket error")

        total_orders = 0
        try:
            orders_r = self.get("/api/resource/Sales Order", params={
                "filters": f'[["customer","=","{customer_id}"],["docstatus","!=",2]]',
                "fields": '["name"]',
                "limit": 500,
            })
            total_orders = len(orders_r.get("data") or [])
        except ERPNextAPIError as exc:
            frappe.log_error(str(exc), "get_dashboard_stats orders error")

        return {
            "open_tickets":   open_count,
            "closed_tickets": closed_count,
            "total_orders":   total_orders,
        }


_client: ERPNextClient | None = None


def get_client() -> ERPNextClient:
    """Return the shared ERPNextClient instance (created on first call)."""
    global _client
    if _client is None:
        _client = ERPNextClient()
    return _client
