# backend/app/services/sla_monitor.py
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.models.sla import SlaPolicy
from app.core.constants import SLA_GREEN_THRESHOLD, SLA_AMBER_THRESHOLD


def compute_sla_timestamps(ticket: Ticket, db: Session) -> None:
    """
    Look up SlaPolicy for ticket.priority, compute response_by and resolution_by.
    Mutates ticket in-place (caller must commit).
    Skips if policy not found.
    """
    policy = db.query(SlaPolicy).filter(SlaPolicy.priority == ticket.priority).first()
    if not policy or not ticket.created_at:
        return
    response_hours = float(policy.response_hours)
    resolution_hours = float(policy.resolution_hours)
    ticket.response_by = ticket.created_at + timedelta(hours=response_hours)
    ticket.resolution_by = ticket.created_at + timedelta(hours=resolution_hours)


def get_sla_status(ticket: Ticket) -> dict:
    """
    Compute current SLA state from ticket fields.

    Returns:
      {
        "state": "green" | "amber" | "red" | "breached" | "met" | "unknown",
        "percent_remaining": float | None,   # 0-100, percentage of resolution window left
        "hours_remaining": float | None,     # hours until resolution_by (negative if past)
        "resolution_by": datetime | None,
        "response_by": datetime | None,
      }
    """
    if not ticket.resolution_by:
        return {
            "state": "unknown",
            "percent_remaining": None,
            "hours_remaining": None,
            "resolution_by": None,
            "response_by": ticket.response_by,
            "paused_total_seconds": getattr(ticket, "sla_paused_total_seconds", 0) or 0,
        }

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created_at = ticket.created_at
    resolution_by = ticket.resolution_by

    # For resolved/closed tickets: check if resolved on time
    if ticket.status in ("Resolved", "Closed"):
        resolved_at = ticket.resolved_at or ticket.closed_at or now
        state = "met" if resolved_at <= resolution_by else "breached"
        return {
            "state": state,
            "percent_remaining": None,
            "hours_remaining": None,
            "resolution_by": resolution_by,
            "response_by": ticket.response_by,
            "paused_total_seconds": getattr(ticket, "sla_paused_total_seconds", 0) or 0,
        }

    # For open tickets
    total_seconds = (resolution_by - created_at).total_seconds()

    # If currently paused (status == "Waiting" with sla_paused_at set), the
    # clock is frozen: treat remaining time as of when the pause started.
    if ticket.status == "Waiting" and getattr(ticket, "sla_paused_at", None):
        effective_now = ticket.sla_paused_at
    else:
        effective_now = now

    remaining_seconds = (resolution_by - effective_now).total_seconds()

    if total_seconds <= 0:
        percent_remaining = 0.0
    else:
        percent_remaining = max(0.0, (remaining_seconds / total_seconds) * 100.0)

    hours_remaining = remaining_seconds / 3600.0

    if remaining_seconds <= 0:
        state = "breached"
    elif percent_remaining <= SLA_AMBER_THRESHOLD:
        state = "red"
    elif percent_remaining <= SLA_GREEN_THRESHOLD:
        state = "amber"
    else:
        state = "green"

    return {
        "state": state,
        "percent_remaining": round(percent_remaining, 2),
        "hours_remaining": round(hours_remaining, 2),
        "resolution_by": resolution_by,
        "response_by": ticket.response_by,
        "paused_total_seconds": getattr(ticket, "sla_paused_total_seconds", 0) or 0,
    }
