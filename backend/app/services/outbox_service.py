# backend/app/services/outbox_service.py
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.email_outbox import EmailOutbox
from app.services.email_sender import send_email


def drain_outbox(db: Session) -> dict:
    """
    Process pending EmailOutbox records: send via SMTP, handle retry/backoff.

    Picks up to 50 records per call that are pending, not exhausted, and past
    their scheduled_at time. Each record is flipped to 'sending' before the
    SMTP call so a concurrent worker won't double-send.

    Backoff after each failure (based on post-increment retry_count):
        retry_count 1 → +15 min   (5 * 3^1)
        retry_count 2 → +45 min   (5 * 3^2)
        retry_count 3 = max_retries → status 'failed'
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    pending = db.query(EmailOutbox).filter(
        EmailOutbox.status == "pending",
        EmailOutbox.retry_count < EmailOutbox.max_retries,
        EmailOutbox.scheduled_at <= now,
    ).limit(50).all()

    sent_count = 0
    failed_count = 0

    for outbox in pending:
        outbox.status = "sending"
        db.commit()

        try:
            result = send_email(
                to=outbox.recipient_email,
                subject=outbox.subject,
                body_html=outbox.body_html or "",
                body_text=outbox.body_text,
                db=db,
            )
            if result is not None:
                outbox.status = "sent"
                outbox.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                sent_count += 1
            else:
                raise Exception("send_email returned None")

        except Exception as exc:
            outbox.retry_count += 1
            outbox.last_error = str(exc)[:2000]
            if outbox.retry_count >= outbox.max_retries:
                outbox.status = "failed"
                outbox.failed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                failed_count += 1
            else:
                outbox.status = "pending"
                delay_minutes = 5 * (3 ** outbox.retry_count)
                outbox.scheduled_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=delay_minutes)

        db.commit()

    return {"sent": sent_count, "failed": failed_count, "processed": len(pending)}
