"""Celery tasks for AI features."""
import asyncio
import logging
import time

from app.tasks.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ai_tasks.classify_ticket_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def classify_ticket_task(self, ticket_id: int):
    """Classify a ticket via Groq AI. Retries up to 2× on transient failures."""
    db = SessionLocal()
    try:
        from app.models.ticket import Ticket
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.is_deleted == False).first()
        if not ticket:
            logger.warning("classify_ticket_task: ticket_id=%s not found", ticket_id)
            return None

        from app.models.ai_prediction import TicketAiPrediction
        from app.schemas.ai import AiPredictionOut
        prediction = (
            db.query(TicketAiPrediction)
            .filter(TicketAiPrediction.ticket_id == ticket.id)
            .order_by(TicketAiPrediction.id.desc())
            .first()
        )
        if prediction:
            result = AiPredictionOut.model_validate(prediction)
            outcome = "reused_existing_prediction"
        else:
            from app.services.ai.classifier import classify_ticket
            started = time.monotonic()
            result = asyncio.run(
                classify_ticket(
                    ticket_id=ticket.id,
                    subject=ticket.subject,
                    description=ticket.description or "",
                    ticket_type=ticket.ticket_type,
                    org_id=ticket.org_id,
                    db=db,
                )
            )
            outcome = "classified" if result else "provider_or_validation_failure"
            logger.info(
                "AI prediction finished ticket_id=%s task_id=%s outcome=%s latency_ms=%.2f",
                ticket_id,
                self.request.id,
                outcome,
                (time.monotonic() - started) * 1000,
            )

        if result:
            from app.services.ai_assignment import (
                reevaluate_assignment_after_prediction,
            )
            evaluation = reevaluate_assignment_after_prediction(
                ticket.id,
                result.id,
                db,
            )
            logger.info(
                "classify_ticket_task ticket_id=%s task_id=%s category=%s evaluation=%s",
                ticket_id,
                self.request.id,
                result.predicted_category,
                evaluation.get("outcome"),
            )
        return result.model_dump() if result else None
    except Exception as exc:
        from app.services.ai.groq_client import AIProviderTransientError

        if isinstance(exc, AIProviderTransientError):
            logger.warning(
                "Transient AI failure ticket_id=%s task_id=%s category=%s",
                ticket_id,
                self.request.id,
                type(exc).__name__,
            )
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                logger.error(
                    "AI retries exhausted ticket_id=%s task_id=%s",
                    ticket_id,
                    self.request.id,
                )
                return None

        # Invalid local/provider data and authorisation/configuration failures
        # cannot succeed unchanged and must not be retried.
        logger.exception(
            "Non-retryable AI task failure ticket_id=%s task_id=%s category=%s",
            ticket_id,
            self.request.id,
            type(exc).__name__,
        )
        db.rollback()
        return None
    finally:
        db.close()
