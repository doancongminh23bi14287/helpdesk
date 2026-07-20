import logging
import time

from app.config import settings
from app.core.redis_client import redis_client
from app.database import SessionLocal
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_ALERT_STATES = {"red", "breached"}


def _reminder_key(ticket_id: int, state: str, recipient_scope: str) -> str:
    return f"sla:alert:{ticket_id}:{state}:{recipient_scope}"


def _reserve_same_state_reminder(key: str) -> bool:
    """Reserve a reminder slot; Redis failure suppresses uncertain repeats."""
    if not settings.SLA_REPEAT_ALERTS_ENABLED:
        return False
    try:
        return bool(
            redis_client.set(
                key,
                "1",
                nx=True,
                ex=settings.SLA_ALERT_REPEAT_SECONDS,
            )
        )
    except Exception as exc:
        logger.warning(
            "SLA reminder dedup unavailable key=%s error=%s; reminder skipped",
            key,
            type(exc).__name__,
        )
        return False


def _refresh_transition_key(key: str) -> None:
    """Best-effort marker after an important transition notification."""
    try:
        redis_client.setex(key, settings.SLA_ALERT_REPEAT_SECONDS, "1")
    except Exception as exc:
        logger.warning(
            "SLA transition dedup marker failed key=%s error=%s",
            key,
            type(exc).__name__,
        )


@celery_app.task(name="app.tasks.sla_checker.check_sla")
def check_sla():
    """Update SLA states and send transition alerts plus TTL-limited reminders."""
    started = time.monotonic()
    db = SessionLocal()
    reminders = 0
    entering_red = 0
    entering_breached = 0
    transition_keys: list[str] = []
    try:
        from app.models.ticket import Ticket
        from app.models.user import User
        from app.services.notify import create_notification
        from app.services.sla_monitor import get_sla_status

        open_tickets = db.query(Ticket).filter(
            Ticket.status.in_(["Open", "In Progress", "Waiting"]),
            Ticket.is_deleted.is_(False),
            Ticket.resolution_by.isnot(None),
        ).all()
        admins = None

        for ticket in open_tickets:
            status_info = get_sla_status(ticket)
            new_state = status_info["state"]
            old_state = ticket.sla_state
            if new_state not in {"green", "amber", "red", "breached"}:
                continue

            ticket.sla_state = new_state
            transitioned = old_state != new_state
            if transitioned:
                logger.info(
                    "SLA state change ticket=%s %s→%s",
                    ticket.id,
                    old_state,
                    new_state,
                    extra={
                        "ticket_id": ticket.id,
                        "old_state": old_state,
                        "new_state": new_state,
                    },
                )

            if new_state == "red" and ticket.assignee_id:
                key = _reminder_key(
                    ticket.id,
                    new_state,
                    f"assignee:{ticket.assignee_id}",
                )
                should_notify = transitioned or _reserve_same_state_reminder(key)
                if not should_notify:
                    continue
                create_notification(
                    db,
                    user_id=ticket.assignee_id,
                    title=(
                        f"SLA at risk: Ticket #{ticket.id}"
                        if transitioned
                        else f"SLA still at risk: Ticket #{ticket.id}"
                    ),
                    content=(
                        f"[sla:red] Ticket #{ticket.id} is in red state. "
                        f"{status_info.get('hours_remaining', 0):.1f}h remaining."
                    ),
                    type="sla",
                    ref_ticket_id=ticket.id,
                )
                if transitioned:
                    entering_red += 1
                    transition_keys.append(key)
                else:
                    reminders += 1

            elif new_state == "breached":
                if admins is None:
                    admins = db.query(User).filter(
                        User.role == "admin",
                        User.is_active.is_(True),
                    ).all()
                any_transition_notification = False
                for admin in admins:
                    key = _reminder_key(
                        ticket.id,
                        new_state,
                        f"admin:{admin.id}",
                    )
                    should_notify = transitioned or _reserve_same_state_reminder(key)
                    if not should_notify:
                        continue
                    create_notification(
                        db,
                        user_id=admin.id,
                        title=(
                            f"SLA BREACHED: Ticket #{ticket.id}"
                            if transitioned
                            else f"SLA breach reminder: Ticket #{ticket.id}"
                        ),
                        content=f"[sla:breached] SLA breached on ticket #{ticket.id}.",
                        type="sla",
                        ref_ticket_id=ticket.id,
                    )
                    if transitioned:
                        any_transition_notification = True
                        transition_keys.append(key)
                    else:
                        reminders += 1
                if transitioned and any_transition_notification:
                    entering_breached += 1

        db.commit()
        for key in transition_keys:
            _refresh_transition_key(key)
        result = {
            "checked": len(open_tickets),
            "entering_red": entering_red,
            "entering_breached": entering_breached,
            "reminders": reminders,
        }
        logger.info(
            "SLA scan finished checked=%s entering_red=%s entering_breached=%s "
            "reminders=%s duration_ms=%.2f",
            len(open_tickets),
            entering_red,
            entering_breached,
            reminders,
            (time.monotonic() - started) * 1000,
        )
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
