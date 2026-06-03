# backend/app/tasks/celery_app.py
from celery import Celery
from celery.schedules import crontab
from app import config

celery_app = Celery(
    "helpdesk",
    broker=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0",
    backend=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0",
    include=[
        "app.tasks.email_poller",
        "app.tasks.sla_checker",
        "app.tasks.subscription_checker",
        "app.tasks.expiry_notifier",
        "app.tasks.invoice_tasks",
        "app.tasks.email_sender_task",
    ],
)

celery_app.conf.beat_schedule = {
    "poll-email-every-2-minutes": {
        "task": "app.tasks.email_poller.poll_email",
        "schedule": 120.0,
    },
    "check-sla-every-5-minutes": {
        "task": "app.tasks.sla_checker.check_sla",
        "schedule": 300.0,
    },
    "check-subscriptions-daily": {
        "task": "app.tasks.subscription_checker.check_subscriptions",
        "schedule": crontab(hour=8, minute=0),  # daily at 08:00 UTC
    },
    "notify-expiring-daily": {
        "task": "app.tasks.expiry_notifier.notify_expiring",
        "schedule": crontab(hour=9, minute=0),  # daily at 09:00 UTC
    },
    "check-overdue-invoices-daily": {
        "task": "app.tasks.invoice_tasks.check_overdue_invoices",
        "schedule": crontab(hour=10, minute=0),
    },
    "auto-generate-invoices-daily": {
        "task": "app.tasks.invoice_tasks.auto_generate_invoices",
        "schedule": crontab(hour=8, minute=30),
    },
}
celery_app.conf.timezone = "UTC"
