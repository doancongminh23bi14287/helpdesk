# backend/app/tasks/email_poller.py
from app.tasks.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="app.tasks.email_poller.poll_email")
def poll_email():
    if not __import__("app.config", fromlist=["settings"]).settings.EMAIL_POLLING_ENABLED:
        return {"processed": 0, "skipped": "email_polling_disabled"}
    db = SessionLocal()
    try:
        from app.services.email_piping import process_inbox
        count = process_inbox(db)
        return {"processed": count}
    finally:
        db.close()
