"""Guarded post-classification assignment recommendation/re-evaluation."""
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_prediction import TicketAiPrediction
from app.models.project import Project, ProjectTask
from app.models.ticket import Ticket, TicketActivity, TicketReply
from app.models.user import User
from app.services.assignment import set_ticket_assignees
from app.services.auto_assign import (
    _release_assignment_lock,
    acquire_assignment_lock,
    score_breakdown,
)
from app.services.notify import create_notification

logger = logging.getLogger(__name__)

_EVALUATED_ACTION = "ai_assignment_evaluated"
_RECOMMENDED_ACTION = "ai_assignment_recommended"
_REASSIGNED_ACTION = "ai_guarded_reassigned"


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _record_evaluation(
    db: Session,
    ticket_id: int,
    prediction_id: int,
    outcome: str,
    recommended_user_id: int | None = None,
) -> None:
    db.add(TicketActivity(
        ticket_id=ticket_id,
        actor_id=None,
        action=_EVALUATED_ACTION,
        from_value=str(prediction_id),
        to_value=str(recommended_user_id) if recommended_user_id else None,
        detail=outcome[:255],
    ))


def _guard_reason(ticket: Ticket, prediction: TicketAiPrediction, db: Session) -> str | None:
    if ticket.assignment_mode != "auto":
        return "manual_or_non_auto_assignment"
    if ticket.status != "Open":
        return "ticket_not_in_early_open_state"
    if prediction.confidence is None or (
        prediction.confidence < settings.AI_ASSIGNMENT_CONFIDENCE_THRESHOLD
    ):
        return "prediction_below_confidence_threshold"
    if ticket.created_at and ticket.created_at < (
        _utc_naive_now()
        - timedelta(minutes=settings.AI_ASSIGNMENT_MAX_TICKET_AGE_MINUTES)
    ):
        return "ticket_too_old"

    staff_reply_exists = (
        db.query(TicketReply.id)
        .outerjoin(User, User.id == TicketReply.author_id)
        .filter(
            TicketReply.ticket_id == ticket.id,
            (
                TicketReply.is_internal.is_(True)
                | User.role.in_(["staff", "admin"])
            ),
        )
        .first()
        is not None
    )
    if staff_reply_exists:
        return "staff_reply_or_internal_note_exists"

    manual_activity_exists = (
        db.query(TicketActivity.id)
        .filter(
            TicketActivity.ticket_id == ticket.id,
            TicketActivity.action == "assigned",
        )
        .first()
        is not None
    )
    if manual_activity_exists:
        return "manual_assignment_activity_exists"

    if ticket.task_id:
        return "ticket_escalated_to_project_task"
    if ticket.project_id:
        project = db.query(Project).filter(Project.id == ticket.project_id).first()
        active_project_task = (
            db.query(ProjectTask.id)
            .filter(
                ProjectTask.project_id == ticket.project_id,
                ProjectTask.status.in_(["open", "working", "review"]),
            )
            .first()
        )
        if (project and project.status == "working") or active_project_task:
            return "project_work_already_active"
    return None


def reevaluate_assignment_after_prediction(
    ticket_id: int,
    prediction_id: int,
    db: Session,
) -> dict:
    """Evaluate once; default mode records a recommendation without changing ownership."""
    started = time.monotonic()
    mode = settings.AI_ASSIGNMENT_REEVALUATION_MODE
    if (
        not settings.AI_ASSIGNMENT_REEVALUATION_ENABLED
        or mode == "off"
    ):
        return {"outcome": "off"}
    if mode not in {"suggest", "auto"}:
        logger.error("Invalid AI assignment reevaluation mode=%s", mode)
        return {"outcome": "invalid_mode"}

    existing = (
        db.query(TicketActivity)
        .filter(
            TicketActivity.ticket_id == ticket_id,
            TicketActivity.action == _EVALUATED_ACTION,
            TicketActivity.from_value == str(prediction_id),
        )
        .first()
    )
    if existing:
        return {"outcome": "already_evaluated"}

    ticket_org = db.query(Ticket.org_id).filter(Ticket.id == ticket_id).scalar()
    if ticket_org is None:
        return {"outcome": "ticket_not_found"}

    lock_key, token, lock_status = acquire_assignment_lock(ticket_org)
    if lock_status is not True:
        # Unlike initial assignment, reevaluation never proceeds without the lock.
        return {
            "outcome": "lock_unavailable" if lock_status is None else "lock_held"
        }

    try:
        ticket = (
            db.query(Ticket)
            .filter(Ticket.id == ticket_id, Ticket.is_deleted.is_(False))
            .with_for_update()
            .first()
        )
        prediction = db.query(TicketAiPrediction).filter(
            TicketAiPrediction.id == prediction_id,
            TicketAiPrediction.ticket_id == ticket_id,
        ).first()
        if not ticket or not prediction:
            db.rollback()
            return {"outcome": "ticket_or_prediction_not_found"}

        existing = (
            db.query(TicketActivity)
            .filter(
                TicketActivity.ticket_id == ticket_id,
                TicketActivity.action == _EVALUATED_ACTION,
                TicketActivity.from_value == str(prediction_id),
            )
            .first()
        )
        if existing:
            db.rollback()
            return {"outcome": "already_evaluated"}

        reason = _guard_reason(ticket, prediction, db)
        if reason:
            _record_evaluation(db, ticket.id, prediction.id, reason)
            db.commit()
            return {"outcome": reason}

        scores = score_breakdown(ticket, db)
        if not scores:
            outcome = "no_eligible_candidate"
            _record_evaluation(db, ticket.id, prediction.id, outcome)
            db.commit()
            return {"outcome": outcome}

        best = scores[0]
        current = next(
            (row for row in scores if row["user_id"] == ticket.assignee_id),
            None,
        )
        current_score = current["total_score"] if current else 0.0
        improvement = round(best["total_score"] - current_score, 2)
        if best["user_id"] == ticket.assignee_id:
            outcome = "current_assignee_remains_best"
            _record_evaluation(db, ticket.id, prediction.id, outcome, best["user_id"])
            db.commit()
            return {"outcome": outcome, "improvement": improvement}
        if improvement < settings.AI_ASSIGNMENT_MIN_SCORE_IMPROVEMENT:
            outcome = "score_improvement_below_threshold"
            _record_evaluation(db, ticket.id, prediction.id, outcome, best["user_id"])
            db.commit()
            return {"outcome": outcome, "improvement": improvement}

        old_assignee_id = ticket.assignee_id
        detail = (
            f"prediction_id={prediction.id}; "
            f"score={best['total_score']:.2f}; improvement={improvement:.2f}"
        )
        if mode == "suggest":
            db.add(TicketActivity(
                ticket_id=ticket.id,
                actor_id=None,
                action=_RECOMMENDED_ACTION,
                from_value=str(old_assignee_id) if old_assignee_id else None,
                to_value=str(best["user_id"]),
                detail=detail[:255],
            ))
            _record_evaluation(
                db, ticket.id, prediction.id, "recommended", best["user_id"]
            )
            db.commit()
            logger.info(
                "AI assignment recommendation ticket_id=%s prediction_id=%s assignee_id=%s",
                ticket.id,
                prediction.id,
                best["user_id"],
            )
            return {
                "outcome": "recommended",
                "recommended_user_id": best["user_id"],
                "improvement": improvement,
            }

        set_ticket_assignees(
            db,
            ticket,
            [best["user_id"]],
            assigned_by=None,
        )
        db.add(TicketActivity(
            ticket_id=ticket.id,
            actor_id=None,
            action=_REASSIGNED_ACTION,
            from_value=str(old_assignee_id) if old_assignee_id else None,
            to_value=str(best["user_id"]),
            detail=detail[:255],
        ))
        _record_evaluation(
            db, ticket.id, prediction.id, "reassigned", best["user_id"]
        )
        chosen = db.query(User).filter(User.id == best["user_id"]).first()
        if chosen:
            chosen.last_assigned_at = _utc_naive_now()
        create_notification(
            db,
            user_id=best["user_id"],
            title=f"Ticket #{ticket.id} assigned to you after routing review",
            content=ticket.subject,
            type="assignment",
            ref_ticket_id=ticket.id,
        )
        db.commit()
        logger.info(
            "AI guarded reassignment ticket_id=%s prediction_id=%s old=%s new=%s",
            ticket.id,
            prediction.id,
            old_assignee_id,
            best["user_id"],
        )
        return {
            "outcome": "reassigned",
            "recommended_user_id": best["user_id"],
            "improvement": improvement,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        _release_assignment_lock(lock_key, token)
        logger.info(
            "AI assignment evaluation finished ticket_id=%s prediction_id=%s duration_ms=%.2f",
            ticket_id,
            prediction_id,
            (time.monotonic() - started) * 1000,
        )
