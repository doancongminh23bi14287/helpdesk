# backend/app/services/auto_assign.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.user import User
from app.models.ticket import Ticket, TicketActivity
from app.models.team import StaffOrgAssignment


def find_best_assignee(ticket: Ticket, db: Session) -> int | None:
    """
    Score every active staff user who is assigned to ticket's org.
    Returns user_id of best candidate, or None if no staff found.

    Scoring (0-100):
      Workload  40%: 40 * (1 - open_count / max_open) where open_count = Open+In Progress+Waiting tickets
      Skill     40%: 40 * (resolved_match / max_resolved) where resolved_match = resolved tickets with
                     same ticket_type OR same priority
      Online    20%: 20 if last_login_at within last 30 min, else 0
    """
    # Get all staff assigned to this org
    assigned_user_ids = db.query(StaffOrgAssignment.user_id).filter(
        StaffOrgAssignment.org_id == ticket.org_id
    ).subquery()

    candidates = db.query(User).filter(
        User.id.in_(select(assigned_user_ids)),
        User.role == "staff",
        User.is_active == True,
    ).all()

    if not candidates:
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC to match DB

    # Compute raw scores
    scores = []
    for agent in candidates:
        # Workload: count of open tickets assigned to this agent
        open_count = db.query(func.count(Ticket.id)).filter(
            Ticket.assignee_id == agent.id,
            Ticket.status.in_(["Open", "In Progress", "Waiting"]),
            Ticket.is_deleted == False,
        ).scalar() or 0

        # Skill: count resolved tickets with same ticket_type OR same priority
        resolved_match = db.query(func.count(Ticket.id)).filter(
            Ticket.assignee_id == agent.id,
            Ticket.status.in_(["Resolved", "Closed"]),
            Ticket.is_deleted == False,
            (
                (Ticket.ticket_type == ticket.ticket_type) |
                (Ticket.priority == ticket.priority)
            ),
        ).scalar() or 0

        # Online: last_login_at within last 30 min
        online = 0
        if agent.last_login_at:
            diff = (now - agent.last_login_at).total_seconds()
            online = 1 if diff <= 1800 else 0

        scores.append({
            "user_id": agent.id,
            "open_count": open_count,
            "resolved_match": resolved_match,
            "online": online,
        })

    if not scores:
        return None

    # Normalise
    max_open = max(s["open_count"] for s in scores) or 1
    max_resolved = max(s["resolved_match"] for s in scores) or 1

    best_id = None
    best_score = -1.0
    for s in scores:
        workload_score = 40.0 * (1.0 - s["open_count"] / max_open)
        skill_score    = 40.0 * (s["resolved_match"] / max_resolved)
        online_score   = 20.0 * s["online"]
        total = workload_score + skill_score + online_score
        if total > best_score:
            best_score = total
            best_id = s["user_id"]

    return best_id


def score_breakdown(ticket: Ticket, db: Session) -> list[dict]:
    """Return full score breakdown for all candidates — used by debug endpoint."""
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

    return sorted(rows, key=lambda x: x["total_score"], reverse=True)
