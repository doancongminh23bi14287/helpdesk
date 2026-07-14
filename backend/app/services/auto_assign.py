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
    ASSIGN_LOCK_TTL_SECONDS,
    SKILL_HISTORICAL_WEIGHT, SKILL_BASELINE_WEIGHT,
    HISTORICAL_POINT_PER_TICKET, SKILL_COLDSTART_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _skill_score(agent_id: int, ticket: Ticket, db: Session) -> float:
    """Hybrid skill score: 0.7×historical + 0.3×baseline, normalised to 0–ASSIGN_SKILL_WEIGHT.

    historical_score: resolved tickets with same AI-predicted category (fallback: ticket_type).
    baseline_score:   cold-start safety net; decays linearly to 0 after SKILL_COLDSTART_THRESHOLD.
    """
    from app.models.ai_prediction import TicketAiPrediction

    # 1. Category of the ticket being assigned (use AI prediction when available)
    current_pred = (
        db.query(TicketAiPrediction)
        .filter(TicketAiPrediction.ticket_id == ticket.id)
        .first()
    )
    target_category = current_pred.predicted_category if current_pred else None

    # 2. Base queryset: tickets this agent has resolved
    resolved_q = (
        db.query(Ticket)
        .join(TicketAssignee, TicketAssignee.ticket_id == Ticket.id)
        .filter(
            TicketAssignee.user_id == agent_id,
            Ticket.status.in_(["Resolved", "Closed"]),
            Ticket.is_deleted == False,  # noqa: E712
        )
    )

    # 3. historical_score — resolved tickets of same category
    if target_category:
        resolved_same = (
            resolved_q
            .join(TicketAiPrediction, TicketAiPrediction.ticket_id == Ticket.id)
            .filter(TicketAiPrediction.predicted_category == target_category)
            .count()
        )
    else:
        # No AI prediction yet — match by raw ticket_type
        resolved_same = resolved_q.filter(Ticket.ticket_type == ticket.ticket_type).count()

    historical_score = min(
        ASSIGN_SKILL_WEIGHT,
        resolved_same * HISTORICAL_POINT_PER_TICKET,
    )

    # 4. baseline_score — cold-start protection
    total_resolved = resolved_q.count()
    baseline_score = max(
        0.0,
        ASSIGN_SKILL_WEIGHT * (1.0 - total_resolved / SKILL_COLDSTART_THRESHOLD),
    )

    # 5. Hybrid
    return round(
        SKILL_HISTORICAL_WEIGHT * historical_score
        + SKILL_BASELINE_WEIGHT * baseline_score,
        2,
    )


def _compute_scores(ticket: Ticket, db: Session) -> list[dict]:
    """Compute raw + normalised scores for all staff candidates assigned to ticket's org."""
    from app.models.project import ProjectMember, ProjectTask

    assigned_user_ids = db.query(StaffOrgAssignment.user_id).filter(
        StaffOrgAssignment.org_id == ticket.org_id
    ).subquery()
    project_member_ids = None
    if ticket.project_id:
        member_ids = [
            row.user_id
            for row in db.query(ProjectMember.user_id).filter(
                ProjectMember.project_id == ticket.project_id,
                ProjectMember.role == "staff",
            ).all()
        ]
        if member_ids:
            project_member_ids = set(member_ids)

    candidates = db.query(User).filter(
        User.id.in_(select(assigned_user_ids)),
        User.role == "staff",
        User.is_active == True,
    ).all()

    rows = []
    for agent in candidates:
        if project_member_ids is not None and agent.id not in project_member_ids:
            continue
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

        # Login time is not presence. Keep the score field stable but neutral
        # until heartbeat-backed presence and privacy policy are implemented.
        online = 0

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

    for r in rows:
        r["workload_score"] = round(ASSIGN_WORKLOAD_WEIGHT * (1.0 - r["open_count"] / max_open), 2)
        r["skill_score"]    = _skill_score(r["user_id"], ticket, db)
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
