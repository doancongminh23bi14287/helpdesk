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


@celery_app.task(name="app.tasks.email_sender_task.notify_new_ticket_async")
def notify_new_ticket_async(
    ticket_id: int,
    subject: str,
    priority: str,
    raised_by_email: str,
    org_name: str,
    service_name: str,
):
    """Send new-ticket emails to admin and creator. Runs in Celery worker."""
    db = SessionLocal()
    try:
        from app.models.ticket import Ticket
        from app.services.email_sender import notify_new_ticket

        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            notify_new_ticket(ticket, org_name=org_name, service_name=service_name, db=db)
    finally:
        db.close()
