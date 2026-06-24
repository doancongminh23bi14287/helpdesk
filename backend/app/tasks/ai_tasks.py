"""Celery tasks for AI features."""
import asyncio
import logging

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

        from app.services.ai.classifier import classify_ticket
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
        if result:
            logger.info(
                "classify_ticket_task: ticket_id=%s → %s/%s",
                ticket_id, result.predicted_category, result.predicted_priority,
            )
        return result.model_dump() if result else None
    except Exception as exc:
        logger.exception("classify_ticket_task failed ticket_id=%s", ticket_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for classify_ticket_task ticket_id=%s", ticket_id)
            return None
    finally:
        db.close()
