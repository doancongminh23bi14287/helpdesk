app_name = "customer_portal"
app_title = "WorkDesk"
app_publisher = "Your Company"
app_description = "Customer-facing portal integrated with ERPNext and Frappe Helpdesk"
app_version = "1.0.0"
app_email = "dev@yourcompany.com"
app_license = "MIT"

# ─── CORS / session ────────────────────────────────────────────────────────────
# Allow portal origin in development
# add_to_cors_headers = ["http://localhost:5173"]

# ─── Scheduled jobs ────────────────────────────────────────────────────────────
scheduler_events = {
    # Poll for inbound support emails every 5 minutes (requires portal_email_account in site config)
    "all": [
        "customer_portal.tasks.poll_email",
    ],
    "daily": [
        "customer_portal.tasks.send_expiry_notifications",
    ],
}

# ─── Doc events ────────────────────────────────────────────────────────────────
doc_events = {
    "HD Ticket": {
        # ticket_events.py lives at the package root to avoid the Python
        # name conflict: hooks.py (file) shadows hooks/ (directory), making
        # customer_portal.hooks.ticket_hooks unreachable as "not a package".
        "on_update": "customer_portal.ticket_events.on_ticket_update",
    },
}
