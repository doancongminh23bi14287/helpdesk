# backend/app/services/auto_assign.py
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.user import User
from app.models.ticket import Ticket, TicketAssignee
from app.models.team import StaffOrgAssignment
from app.core.redis_client import redis_client
from app.core.constants import (
    ASSIGN_WORKLOAD_WEIGHT, ASSIGN_SKILL_WEIGHT, ASSIGN_ONLINE_WEIGHT,
    ASSIGN_ONLINE_WINDOW_SECONDS, ASSIGN_LOCK_TTL_SECONDS,
)

logger = logging.getLogger(__name__)


def _skill_score(agent: User, ticket: Ticket, max_resolved: int) -> float:
    # future: skill-based matching (topic embeddings or tag overlap)
    return 0.0


def _compute_scores(ticket: Ticket, db: Session) -> list[dict]:
    """Compute raw + normalised scores for all staff candidates assigned to ticket's org."""
    from app.models.project import ProjectTask

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
        # Workload = active project tasks; fallback to active tickets via ticket_assignees
        task_count = db.query(func.count(ProjectTask.id)).filter(
            ProjectTask.assignee_id == agent.id,
            ProjectTask.status.in_(["open", "working", "review"]),
        ).scalar() or 0

        if task_count > 0:
            open_count = task_count
        else:
            open_count = db.query(func.count(TicketAssignee.id)).join(
                Ticket, TicketAssignee.ticket_id == Ticket.id
            ).filter(
                TicketAssignee.user_id == agent.id,
                Ticket.status.in_(["Open", "In Progress", "Waiting"]),
                Ticket.is_deleted == False,  # noqa: E712
            ).scalar() or 0

        online = 0
        if agent.last_login_at:
            diff = (now - agent.last_login_at).total_seconds()
            online = 1 if diff <= ASSIGN_ONLINE_WINDOW_SECONDS else 0

        rows.append({
            "user_id": agent.id,
            "full_name": agent.full_name,
            "open_count": open_count,
            "resolved_match": 0,
            "online": online,
            "last_assigned_at": agent.last_assigned_at,
        })

    if not rows:
        return rows

    max_open = max(r["open_count"] for r in rows) or 1
    max_resolved = 1  # _skill_score always returns 0 currently

    for r in rows:
        r["workload_score"] = round(ASSIGN_WORKLOAD_WEIGHT * (1.0 - r["open_count"] / max_open), 2)
        r["skill_score"]    = round(_skill_score(None, ticket, max_resolved), 2)
        r["online_score"]   = round(ASSIGN_ONLINE_WEIGHT * r["online"], 2)
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
    lock_ttl = ASSIGN_LOCK_TTL_SECONDS

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
