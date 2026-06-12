"""
Email router — decides whether an inbound email creates a new ticket
or appends a reply to an existing thread.

Threading strategy:
  1. Dedup: skip emails already seen (by Message-ID).
  2. In-Reply-To / References headers → look up our Email Message Log.
  3. No match → create a new ticket.

Requires a custom DocType 'Email Message Log' with fields:
  - message_id  (Data, unique)
  - ticket_id   (Data)
"""
import frappe
from customer_portal.models.ticket import MessageType
from customer_portal.repositories import message_repository, ticket_repository


def route_inbound_email(parsed: dict) -> dict:
    """
    Route a parsed email dict (from email.parser.parse_raw_email) to a ticket.

    Returns:
        { action: "created" | "appended" | "duplicate", ticket_id: str | None }
    """
    message_id = parsed["message_id"]
    if not message_id:
        return {"action": "skipped", "ticket_id": None}

    # 1. Deduplicate — idempotent processing
    if _already_processed(message_id):
        frappe.logger().debug(f"Email {message_id} already processed — skipping")
        return {"action": "duplicate", "ticket_id": None}

    # 2. Try to find an existing ticket thread
    ticket_id = _resolve_thread(parsed)

    if ticket_id:
        _append_to_thread(ticket_id, parsed)
        _log_message_id(message_id, ticket_id)
        return {"action": "appended", "ticket_id": ticket_id}

    # 3. No thread — open a new ticket
    ticket = _create_ticket_from_email(parsed)
    _log_message_id(message_id, ticket.name)
    return {"action": "created", "ticket_id": ticket.name}


# ── Private ───────────────────────────────────────────────────────────────────

def _already_processed(message_id: str) -> bool:
    """Check the Email Message Log for a duplicate Message-ID."""
    if not frappe.db.exists("DocType", "Email Message Log"):
        return False
    return bool(frappe.db.exists("Email Message Log", {"message_id": message_id}))


def _resolve_thread(parsed: dict) -> str | None:
    """
    Walk In-Reply-To and References headers to find a known ticket.
    First match wins (most-recent-ancestor heuristic).
    """
    if not frappe.db.exists("DocType", "Email Message Log"):
        return None

    candidates = []
    if parsed.get("in_reply_to"):
        candidates.append(parsed["in_reply_to"])
    candidates.extend(parsed.get("references", []))

    for msg_id in candidates:
        ticket_id = frappe.db.get_value(
            "Email Message Log", {"message_id": msg_id}, "ticket_id"
        )
        if ticket_id:
            return ticket_id

    return None


def _append_to_thread(ticket_id: str, parsed: dict):
    """Post the email body as a public reply on the existing ticket."""
    body = parsed.get("body_html") or parsed.get("body_text") or ""
    message_repository.create_message(
        ticket_id=ticket_id,
        content=body,
        author=parsed["from_email"],
        message_type=MessageType.PUBLIC_REPLY,
    )


def _create_ticket_from_email(parsed: dict):
    """Create a new HD Ticket from the inbound email."""
    description = parsed.get("body_html") or parsed.get("body_text") or ""
    return ticket_repository.create_ticket(
        subject=parsed["subject"][:140],
        description=description,
        priority="Medium",
        user_email=parsed["from_email"],
    )


def _log_message_id(message_id: str, ticket_id: str):
    """Persist Message-ID → ticket_id mapping for future thread resolution."""
    if not frappe.db.exists("DocType", "Email Message Log"):
        return
    try:
        log = frappe.new_doc("Email Message Log")
        log.message_id = message_id
        log.ticket_id = ticket_id
        log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as exc:
        frappe.log_error(str(exc), "Email Message Log Insert Error")
