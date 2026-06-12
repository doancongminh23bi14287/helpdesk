"""
Message repository — HD Ticket Comment DB access.
Supports both public replies and internal notes via comment_type field.
"""
import frappe
from customer_portal.models.ticket import MessageType

_COMMENT_FIELDS = ["name", "content", "creation", "commented_by", "comment_type"]


def get_messages(ticket_id: str) -> list:
    """
    Fetch all messages for a ticket, ordered chronologically.
    Returns both public_reply and internal_note types; callers filter as needed.
    """
    return frappe.get_all(
        "HD Ticket Comment",
        filters={"reference_ticket": ticket_id},
        fields=_COMMENT_FIELDS,
        order_by="creation asc",
    )


def get_public_messages(ticket_id: str) -> list:
    """Fetch only customer-visible messages (public replies)."""
    return frappe.get_all(
        "HD Ticket Comment",
        filters={
            "reference_ticket": ticket_id,
            "comment_type": MessageType.PUBLIC_REPLY,
        },
        fields=_COMMENT_FIELDS,
        order_by="creation asc",
    )


def create_message(
    *,
    ticket_id: str,
    content: str,
    author: str,
    message_type: str = MessageType.PUBLIC_REPLY,
):
    """
    Insert a message into a ticket thread.
    message_type must be MessageType.PUBLIC_REPLY or MessageType.INTERNAL_NOTE.
    """
    comment = frappe.new_doc("HD Ticket Comment")
    comment.reference_ticket = ticket_id
    comment.content = content
    comment.commented_by = author
    comment.comment_type = message_type
    comment.insert(ignore_permissions=True)
    frappe.db.commit()
    return comment
