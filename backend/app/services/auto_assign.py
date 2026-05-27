# backend/app/services/auto_assign.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.user import User
from app.models.ticket import Ticket, TicketActivity
from app.models.team import StaffOrgAssignment


def _compute_scores(ticket: Ticket, db: Session) -> list[dict]:
    """Compute raw + normalised scores for all staff candidates assigned to ticket's org."""
    assigned_user_ids = db.query(StaffOrgAssignment.user_id).filter(
        StaffOrgAssignment.org_id == ticket.org_id
    ).subquery()

    candidates = db.query(User).filter(
        User.id.in_(select(assigned_user_ids)),
        User.role == "staff",
        User.is_active == True,
    ).all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for agent in candidates:
        open_count = db.query(func.count(Ticket.id)).filter(
            Ticket.assignee_id == agent.id,
            Ticket.status.in_(["Open", "In Progress", "Waiting"]),
            Ticket.is_deleted == False,
        ).scalar() or 0

        resolved_match = db.query(func.count(Ticket.id)).filter(
            Ticket.assignee_id == agent.id,
            Ticket.status.in_(["Resolved", "Closed"]),
            Ticket.is_deleted == False,
            (
                (Ticket.ticket_type == ticket.ticket_type) |
                (Ticket.priority == ticket.priority)
            ),
        ).scalar() or 0

        online = 0
        if agent.last_login_at:
            diff = (now - agent.last_login_at).total_seconds()
            online = 1 if diff <= 1800 else 0

        rows.append({
            "user_id": agent.id,
            "full_name": agent.full_name,
            "open_count": open_count,
            "resolved_match": resolved_match,
            "online": online,
        })

    if not rows:
        return rows

    max_open = max(r["open_count"] for r in rows) or 1
    max_resolved = max(r["resolved_match"] for r in rows) or 1

    for r in rows:
        r["workload_score"] = round(40.0 * (1.0 - r["open_count"] / max_open), 2)
        r["skill_score"]    = round(40.0 * (r["resolved_match"] / max_resolved), 2)
        r["online_score"]   = round(20.0 * r["online"], 2)
        r["total_score"]    = round(r["workload_score"] + r["skill_score"] + r["online_score"], 2)

    return rows


def find_best_assignee(ticket: Ticket, db: Session) -> int | None:
    """Return user_id of highest-scoring staff candidate, or None."""
    scores = _compute_scores(ticket, db)
    if not scores:
        return None
    return max(scores, key=lambda s: s["total_score"])["user_id"]


def score_breakdown(ticket: Ticket, db: Session) -> list[dict]:
    """Return full score breakdown sorted by total_score desc."""
    return sorted(_compute_scores(ticket, db), key=lambda x: x["total_score"], reverse=True)
