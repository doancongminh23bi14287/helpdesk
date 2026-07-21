# backend/app/tasks/email_outbox_task.py
import logging
from app.tasks.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.email_outbox_task.process_email_outbox")
def process_email_outbox():
    if not __import__("app.config", fromlist=["settings"]).settings.EMAIL_SENDING_ENABLED:
        return {"sent": 0, "failed": 0, "processed": 0, "skipped": "email_sending_disabled"}
    """Drain pending EmailOutbox records via SMTP with exponential-backoff retry."""
    db = SessionLocal()
    try:
        from app.services.outbox_service import drain_outbox
        result = drain_outbox(db)
        logger.info(
            "Email outbox: sent=%s failed=%s processed=%s",
            result.get("sent", 0), result.get("failed", 0), result.get("processed", 0),
        )
        return result
    finally:
        db.close()
