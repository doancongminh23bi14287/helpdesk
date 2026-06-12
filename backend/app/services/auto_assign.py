# backend/app/services/auto_assign.py
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.user import User
from app.models.ticket import Ticket
from app.models.team import StaffOrgAssignment
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


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
            "last_assigned_at": agent.last_assigned_at,
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


def _do_find_best_assignee(ticket: Ticket, db: Session) -> int | None:
    """Score all candidates and return the winning user_id with deterministic tie-breaking."""
    scores = _compute_scores(ticket, db)
    if not scores:
        return None

    max_score = max(s["total_score"] for s in scores)
    top_candidates = [s for s in scores if s["total_score"] == max_score]

    if len(top_candidates) == 1:
        winner = top_candidates[0]
    else:
        # Tie-breaker: prefer the agent least recently assigned.
        # last_assigned_at = None means never assigned — highest priority.
        winner = min(
            top_candidates,
            key=lambda s: s["last_assigned_at"] or datetime.min,
        )

    logger.info(
        "Ticket %s assigned to user %s (score=%s)",
        ticket.id, winner["user_id"], winner["total_score"],
        extra={"ticket_id": ticket.id, "assignee_id": winner["user_id"]},
    )
    return winner["user_id"]


def find_best_assignee(ticket: Ticket, db: Session) -> int | None:
    """Return user_id of highest-scoring staff candidate, or None.

    Uses a short-TTL Redis lock per org to prevent two simultaneous ticket
    creations from assigning the same agent twice.
    """
    lock_key = f"assignment:org:{ticket.org_id}"
    lock_ttl = 10  # seconds — enough for the scoring query

    acquired = redis_client.set(lock_key, "1", nx=True, ex=lock_ttl)
    if not acquired:
        # Another ticket is being assigned for this org right now.
        # Wait briefly and retry once before proceeding without the lock.
        time.sleep(0.2)
        acquired = redis_client.set(lock_key, "1", nx=True, ex=lock_ttl)

    try:
        return _do_find_best_assignee(ticket, db)
    finally:
        if acquired:
            redis_client.delete(lock_key)


def score_breakdown(ticket: Ticket, db: Session) -> list[dict]:
    """Return full score breakdown sorted by total_score desc."""
    return sorted(_compute_scores(ticket, db), key=lambda x: x["total_score"], reverse=True)
