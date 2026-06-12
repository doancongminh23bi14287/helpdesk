# backend/app/tasks/sla_checker.py
import logging
from app.tasks.celery_app import celery_app
from app.core.redis_client import redis_client
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.sla_checker.check_sla")
def check_sla():
    """
    Check all open tickets. Update sla_state. Create notifications for red/breached.
    Dedup: don't re-notify same ticket+state within 1 hour.
    """
    db = SessionLocal()
    try:
        from app.models.ticket import Ticket
        from app.models.user import User
        from app.services.sla_monitor import get_sla_status
        from app.services.notify import create_notification

        open_tickets = db.query(Ticket).filter(
            Ticket.status.in_(["Open", "In Progress", "Waiting"]),
            Ticket.is_deleted == False,
            Ticket.resolution_by != None,
        ).all()

        for ticket in open_tickets:
            status_info = get_sla_status(ticket)
            new_state = status_info["state"]

            # Update sla_state on ticket
            if new_state in ("green", "amber", "red", "breached"):
                old_state = ticket.sla_state
                ticket.sla_state = new_state
                if old_state != new_state:
                    logger.info(
                        "SLA state change ticket=%s %s→%s",
                        ticket.id, old_state, new_state,
                        extra={"ticket_id": ticket.id, "old_state": old_state, "new_state": new_state},
                    )

            # Notify on red or breached — dedup within 1 hour
            if new_state in ("red", "breached"):
                # Redis dedup key prevents repeated SLA alerts.
                # Key format: sla:{ticket_id}:{state}
                # TTL: 3600s (1 hour) — agent receives at most 1 alert/hour per state.
                dedup_key = f"sla:{ticket.id}:{new_state}"

                if redis_client.exists(dedup_key):
                    continue  # already notified within last hour, skip

                if new_state == "red" and ticket.assignee_id:
                    create_notification(
                        db,
                        user_id=ticket.assignee_id,
                        title=f"SLA at risk: Ticket #{ticket.id}",
                        content=f"[sla:red] Ticket #{ticket.id} is in red state. "
                                f"{status_info.get('hours_remaining', 0):.1f}h remaining.",
                        type="sla",
                        ref_ticket_id=ticket.id,
                    )
                elif new_state == "breached":
                    # Notify all admins
                    admins = db.query(User).filter(
                        User.role == "admin",
                        User.is_active == True,
                    ).all()
                    for admin in admins:
                        create_notification(
                            db,
                            user_id=admin.id,
                            title=f"SLA BREACHED: Ticket #{ticket.id}",
                            content=f"[sla:breached] SLA breached on ticket #{ticket.id}.",
                            type="sla",
                            ref_ticket_id=ticket.id,
                        )

                # Set dedup key AFTER notifications are queued (before commit is fine —
                # Redis write is independent of the DB transaction).
                redis_client.setex(dedup_key, 3600, "1")

        db.commit()
        return {"checked": len(open_tickets)}
    finally:
        db.close()
