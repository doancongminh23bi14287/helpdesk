"""Celery task: send outbound email asynchronously."""
from app.tasks.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="app.tasks.email_sender_task.send_email_async")
def send_email_async(to: str, subject: str, body_html: str, body_text: str = None):
    db = SessionLocal()
    try:
        from app.services.email_sender import send_email
        send_email(to, subject, body_html, body_text=body_text, db=db)
    finally:
        db.close()
