"""
Email listener — polls an IMAP inbox and dispatches each unseen message
through the email router to create or append to tickets.

Called every 5 minutes by the Frappe scheduler (see hooks.py).

Site config key (common_site_config.json or site_config.json):

  "portal_email_account": {
      "host":     "imap.example.com",
      "port":     993,
      "username": "support@example.com",
      "password": "secret",
      "folder":   "INBOX"      # optional, defaults to INBOX
  }
"""
import imaplib
import frappe

from customer_portal.email.parser import parse_raw_email
from customer_portal.email.router import route_inbound_email


def poll_inbound_email():
    """
    Main entry point — called by tasks.py on a scheduled interval.
    Fetches UNSEEN messages from IMAP and routes each one.
    Marks messages as Seen only after successful routing.
    """
    config = _load_config()
    if not config:
        # Email piping is not configured for this site — nothing to do.
        return

    try:
        conn = _connect(config)
        _process_unseen(conn)
        conn.logout()
    except imaplib.IMAP4.error as exc:
        frappe.log_error(str(exc), "Email Listener IMAP Error")
    except Exception as exc:
        frappe.log_error(str(exc), "Email Listener Unexpected Error")


# ── Private ───────────────────────────────────────────────────────────────────

def _load_config() -> dict | None:
    """Read IMAP credentials from Frappe site config."""
    try:
        return frappe.get_site_config().get("portal_email_account")
    except Exception:
        return None


def _connect(config: dict) -> imaplib.IMAP4_SSL:
    host = config["host"]
    port = int(config.get("port", 993))
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(config["username"], config["password"])
    conn.select(config.get("folder", "INBOX"))
    return conn


def _extract_rfc822_payload(raw_data) -> bytes | None:
    """
    IMAP fetch returns a list whose first item is either a (header, body) tuple
    or a bare bytes flag. Narrow the type and pull the RFC822 body, or None.
    """
    if not raw_data:
        return None
    first = raw_data[0]
    if isinstance(first, tuple) and len(first) >= 2 and isinstance(first[1], bytes):
        return first[1]
    return None


def _process_unseen(conn: imaplib.IMAP4_SSL):
    """Iterate UNSEEN messages and route each one."""
    _, data = conn.search(None, "UNSEEN")
    msg_ids = data[0].split() if data and data[0] else []

    for seq_id in msg_ids:
        try:
            _, raw_data = conn.fetch(seq_id, "(RFC822)")
            raw_bytes = _extract_rfc822_payload(raw_data)
            if raw_bytes is None:
                continue

            parsed = parse_raw_email(raw_bytes)
            result = route_inbound_email(parsed)

            frappe.logger().info(
                f"[EmailListener] {result['action']} — ticket={result.get('ticket_id')} "
                f"from={parsed.get('from_email')} subject={parsed.get('subject', '')[:60]}"
            )

            # Mark as Seen only on success (prevents message loss on crash)
            conn.store(seq_id, "+FLAGS", "\\Seen")

        except Exception as exc:
            frappe.log_error(str(exc), f"Email Listener: error processing message {seq_id}")
            # Do NOT mark as Seen — will be retried on next poll
