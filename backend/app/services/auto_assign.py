# backend/app/services/auto_assign.py
import logging
import time
import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.core.constants import (
    ASSIGN_LOCK_TTL_SECONDS,
    ASSIGN_ONLINE_WEIGHT,
    ASSIGN_SKILL_WEIGHT,
    ASSIGN_WORKLOAD_WEIGHT,
    HISTORICAL_POINT_PER_TICKET,
    SKILL_BASELINE_WEIGHT,
    SKILL_COLDSTART_THRESHOLD,
    SKILL_HISTORICAL_WEIGHT,
)
from app.core.redis_client import redis_client
from app.models.ai_prediction import TicketAiPrediction
from app.models.project import ProjectMember, ProjectTask, TaskAssignee
from app.models.team import StaffOrgAssignment
from app.models.ticket import Ticket, TicketAssignee
from app.models.user import User
from app.services.presence import get_present_user_ids

logger = logging.getLogger(__name__)

ACTIVE_TICKET_STATUSES = ("Open", "In Progress", "Waiting")
ACTIVE_TASK_STATUSES = ("open", "working", "review")
TERMINAL_TICKET_STATUSES = ("Resolved", "Closed")


def _candidate_users(ticket: Ticket, db: Session) -> list[User]:
    """Return active organisation staff, narrowed by explicit project staff membership."""
    candidates = (
        db.query(User)
        .join(StaffOrgAssignment, StaffOrgAssignment.user_id == User.id)
        .filter(
            StaffOrgAssignment.org_id == ticket.org_id,
            User.role == "staff",
            User.is_active.is_(True),
        )
        .distinct()
        .all()
    )
    if not ticket.project_id:
        return candidates

    member_ids = {
        row.user_id
        for row in db.query(ProjectMember.user_id).filter(
            ProjectMember.project_id == ticket.project_id,
            ProjectMember.role.in_(["staff", "manager"]),
        ).all()
    }
    if not member_ids:
        return candidates
    return [candidate for candidate in candidates if candidate.id in member_ids]


def _workload_counts(candidate_ids: list[int], db: Session) -> tuple[dict[int, int], dict[int, int]]:
    """Batch active ticket and task assignment counts for each candidate."""
    if not candidate_ids:
        return {}, {}

    ticket_counts = dict(
        db.query(
            TicketAssignee.user_id,
            func.count(func.distinct(Ticket.id)),
        )
        .join(Ticket, Ticket.id == TicketAssignee.ticket_id)
        .filter(
            TicketAssignee.user_id.in_(candidate_ids),
            Ticket.status.in_(ACTIVE_TICKET_STATUSES),
            Ticket.is_deleted.is_(False),
        )
        .group_by(TicketAssignee.user_id)
        .all()
    )
    primary_task_assignments = (
        db.query(
            ProjectTask.assignee_id.label("user_id"),
            ProjectTask.id.label("task_id"),
        )
        .filter(
            ProjectTask.assignee_id.in_(candidate_ids),
            ProjectTask.status.in_(ACTIVE_TASK_STATUSES),
        )
    )
    multi_task_assignments = (
        db.query(
            TaskAssignee.user_id.label("user_id"),
            TaskAssignee.task_id.label("task_id"),
        )
        .join(ProjectTask, ProjectTask.id == TaskAssignee.task_id)
        .filter(
            TaskAssignee.user_id.in_(candidate_ids),
            ProjectTask.status.in_(ACTIVE_TASK_STATUSES),
        )
    )
    active_task_assignments = primary_task_assignments.union(
        multi_task_assignments
    ).subquery()
    task_counts = dict(
        db.query(
            active_task_assignments.c.user_id,
            func.count(func.distinct(active_task_assignments.c.task_id)),
        )
        .group_by(active_task_assignments.c.user_id)
        .all()
    )
    return ticket_counts, task_counts


def _target_category(ticket: Ticket, db: Session) -> tuple[str | None, bool]:
    """Return latest valid AI category, otherwise the human ticket type."""
    prediction = (
        db.query(TicketAiPrediction)
        .filter(
            TicketAiPrediction.ticket_id == ticket.id,
            TicketAiPrediction.predicted_category != "unclassified",
        )
        .order_by(TicketAiPrediction.id.desc())
        .first()
    )
    if prediction:
        return prediction.predicted_category, True
    return ticket.ticket_type, False


def _skill_scores(
    candidate_ids: list[int],
    ticket: Ticket,
    db: Session,
) -> dict[int, float]:
    """Compute tenant-scoped hybrid skill scores using aggregate queries."""
    if not candidate_ids:
        return {}

    resolved_base = (
        db.query(
            TicketAssignee.user_id.label("user_id"),
            func.count(func.distinct(Ticket.id)).label("ticket_count"),
        )
        .join(Ticket, Ticket.id == TicketAssignee.ticket_id)
        .filter(
            TicketAssignee.user_id.in_(candidate_ids),
            Ticket.org_id == ticket.org_id,
            Ticket.status.in_(TERMINAL_TICKET_STATUSES),
            Ticket.is_deleted.is_(False),
        )
    )
    total_resolved = dict(
        resolved_base.group_by(TicketAssignee.user_id).all()
    )

    target, uses_ai_category = _target_category(ticket, db)
    same_counts: dict[int, int] = {}
    if target:
        same_query = (
            db.query(
                TicketAssignee.user_id,
                func.count(func.distinct(Ticket.id)),
            )
            .join(Ticket, Ticket.id == TicketAssignee.ticket_id)
            .filter(
                TicketAssignee.user_id.in_(candidate_ids),
                Ticket.org_id == ticket.org_id,
                Ticket.status.in_(TERMINAL_TICKET_STATUSES),
                Ticket.is_deleted.is_(False),
            )
        )
        if uses_ai_category:
            latest_ids = (
                db.query(
                    TicketAiPrediction.ticket_id.label("ticket_id"),
                    func.max(TicketAiPrediction.id).label("prediction_id"),
                )
                .group_by(TicketAiPrediction.ticket_id)
                .subquery()
            )
            latest_prediction = aliased(TicketAiPrediction)
            same_query = (
                same_query
                .join(latest_ids, latest_ids.c.ticket_id == Ticket.id)
                .join(latest_prediction, latest_prediction.id == latest_ids.c.prediction_id)
                .filter(latest_prediction.predicted_category == target)
            )
        else:
            same_query = same_query.filter(Ticket.ticket_type == target)
        same_counts = dict(
            same_query.group_by(TicketAssignee.user_id).all()
        )

    scores: dict[int, float] = {}
    for user_id in candidate_ids:
        historical_score = min(
            ASSIGN_SKILL_WEIGHT,
            same_counts.get(user_id, 0) * HISTORICAL_POINT_PER_TICKET,
        )
        baseline_score = max(
            0.0,
            ASSIGN_SKILL_WEIGHT
            * (1.0 - total_resolved.get(user_id, 0) / SKILL_COLDSTART_THRESHOLD),
        )
        scores[user_id] = round(
            SKILL_HISTORICAL_WEIGHT * historical_score
            + SKILL_BASELINE_WEIGHT * baseline_score,
            2,
        )
    return scores


def _compute_scores(ticket: Ticket, db: Session) -> list[dict]:
    """Compute explainable 40/40/20 scores for all eligible staff."""
    started = time.monotonic()
    candidates = _candidate_users(ticket, db)
    candidate_ids = [candidate.id for candidate in candidates]
    if not candidate_ids:
        return []

    ticket_counts, task_counts = _workload_counts(candidate_ids, db)
    skill_scores = _skill_scores(candidate_ids, ticket, db)
    present_user_ids = get_present_user_ids(candidate_ids)

    rows = []
    for candidate in candidates:
        active_ticket_count = ticket_counts.get(candidate.id, 0)
        active_task_count = task_counts.get(candidate.id, 0)
        load_units = active_ticket_count + active_task_count
        rows.append({
            "user_id": candidate.id,
            "full_name": candidate.full_name,
            "active_ticket_count": active_ticket_count,
            "active_task_count": active_task_count,
            "load_units": load_units,
            # Backward-compatible field retained for current clients.
            "open_count": load_units,
            "resolved_match": 0,
            "online": int(candidate.id in present_user_ids),
            "last_assigned_at": candidate.last_assigned_at,
        })

    maximum_load = max(row["load_units"] for row in rows)
    normalizer = max(1, maximum_load)
    for row in rows:
        row["workload_score"] = round(
            ASSIGN_WORKLOAD_WEIGHT * (1.0 - row["load_units"] / normalizer),
            2,
        )
        row["skill_score"] = skill_scores[row["user_id"]]
        row["online_score"] = round(ASSIGN_ONLINE_WEIGHT * row["online"], 2)
        row["total_score"] = round(
            row["workload_score"] + row["skill_score"] + row["online_score"],
            2,
        )

    logger.info(
        "Assignment scores computed ticket_id=%s candidate_count=%s duration_ms=%.2f",
        ticket.id,
        len(rows),
        (time.monotonic() - started) * 1000,
    )
    return rows


def _winner_sort_key(score: dict) -> tuple:
    last_assigned = score["last_assigned_at"]
    return (
        -score["total_score"],
        last_assigned is not None,
        last_assigned or datetime.min,
        score["user_id"],
    )


def _do_find_best_assignee(ticket: Ticket, db: Session) -> int | None:
    scores = _compute_scores(ticket, db)
    if not scores:
        return None
    winner = min(scores, key=_winner_sort_key)
    logger.info(
        "Ticket %s assigned to user %s (score=%s)",
        ticket.id,
        winner["user_id"],
        winner["total_score"],
        extra={
            "ticket_id": ticket.id,
            "assignee_id": winner["user_id"],
            "candidate_count": len(scores),
            "chosen_score": winner["total_score"],
        },
    )
    return winner["user_id"]


def _release_assignment_lock(lock_key: str, token: str) -> None:
    """Compare-and-delete so this process never releases another owner's lock."""
    try:
        redis_client.eval(
            """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            end
            return 0
            """,
            1,
            lock_key,
            token,
        )
    except Exception as exc:
        logger.warning(
            "Assignment lock release failed org_lock=%s error=%s",
            lock_key,
            type(exc).__name__,
        )


def acquire_assignment_lock(org_id: int) -> tuple[str, str, bool | None]:
    """Return (key, token, status): True acquired, False held, None Redis unavailable."""
    lock_key = f"assignment:org:{org_id}"
    token = uuid.uuid4().hex
    try:
        acquired = bool(
            redis_client.set(
                lock_key,
                token,
                nx=True,
                ex=ASSIGN_LOCK_TTL_SECONDS,
            )
        )
        if not acquired:
            time.sleep(0.2)
            acquired = bool(
                redis_client.set(
                    lock_key,
                    token,
                    nx=True,
                    ex=ASSIGN_LOCK_TTL_SECONDS,
                )
            )
        return lock_key, token, acquired
    except Exception as exc:
        logger.warning(
            "Assignment lock unavailable org_id=%s error=%s",
            org_id,
            type(exc).__name__,
        )
        return lock_key, token, None


def find_best_assignee(ticket: Ticket, db: Session) -> int | None:
    """Select under an organisation lock; retained for non-transaction callers."""
    return _find_best_assignee(ticket, db, hold_lock=False)


def _find_best_assignee(ticket: Ticket, db: Session, *, hold_lock: bool) -> int | None:
    lock_key, token, lock_status = acquire_assignment_lock(ticket.org_id)
    if lock_status is False:
        logger.info("Assignment deferred because org lock is held org_id=%s", ticket.org_id)
        return None
    if lock_status is None:
        logger.warning("Initial assignment left unassigned because Redis lock is unavailable org_id=%s", ticket.org_id)
        return None
    if hold_lock:
        db.info["assignment_lock"] = (lock_key, token)
        try:
            return _do_find_best_assignee(ticket, db)
        except Exception:
            db.info.pop("assignment_lock", None)
            _release_assignment_lock(lock_key, token)
            raise
    try:
        return _do_find_best_assignee(ticket, db)
    finally:
        _release_assignment_lock(lock_key, token)


def find_best_assignee_for_transaction(ticket: Ticket, db: Session) -> int | None:
    """Select a winner and retain the org lock until the caller commits."""
    return _find_best_assignee(ticket, db, hold_lock=True)


def release_transaction_assignment_lock(db: Session) -> None:
    """Release a transaction-held lock after commit or rollback."""
    lock = db.info.pop("assignment_lock", None)
    if lock:
        _release_assignment_lock(*lock)


def score_breakdown(ticket: Ticket, db: Session) -> list[dict]:
    """Return score components in the same deterministic order used for selection."""
    return sorted(_compute_scores(ticket, db), key=_winner_sort_key)
