# backend/app/tasks/celery_app.py
from celery import Celery
from app import config

celery_app = Celery(
    "helpdesk",
    broker=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0",
    backend=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0",
    include=["app.tasks.email_poller", "app.tasks.sla_checker"],
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
}
celery_app.conf.timezone = "UTC"
