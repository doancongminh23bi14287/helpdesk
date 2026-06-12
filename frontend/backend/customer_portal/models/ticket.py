"""
Ticket domain model: status/priority constants and message types.
Single source of truth — never hardcode these strings elsewhere.
"""


class TicketStatus:
    OPEN = "Open"
    PENDING = "Pending"
    REPLIED = "Replied"
    RESOLVED = "Resolved"
    CLOSED = "Closed"

    ALL = [OPEN, PENDING, REPLIED, RESOLVED, CLOSED]
    # Statuses where no new customer reply is allowed
    TERMINAL = [RESOLVED, CLOSED]
    # Statuses where a customer reply should reopen the ticket
    REOPEN_ON_REPLY = [RESOLVED, REPLIED]


class TicketPriority:
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"

    ALL = [LOW, MEDIUM, HIGH, URGENT]
    DEFAULT = MEDIUM


class MessageType:
    PUBLIC_REPLY = "public_reply"
    INTERNAL_NOTE = "internal_note"
