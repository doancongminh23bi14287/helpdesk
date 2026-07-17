# backend/app/tasks/sla_checker.py
import logging
from app.tasks.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.sla_checker.check_sla")
def check_sla():
    """
    Check all open tickets. Update sla_state. Create notifications for red/breached.
    Notify only when a ticket enters an at-risk or breached SLA state.
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

            old_state = ticket.sla_state
            if new_state in ("green", "amber", "red", "breached"):
                ticket.sla_state = new_state
                if old_state != new_state:
                    logger.info(
                        "SLA state change ticket=%s %s→%s",
                        ticket.id, old_state, new_state,
                        extra={"ticket_id": ticket.id, "old_state": old_state, "new_state": new_state},
                    )

            # An alert is actionable when the ticket enters red/breached. Repeating
            # it every checker interval floods the recipient without new information.
            if old_state == new_state or new_state not in ("red", "breached"):
                continue

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

        db.commit()
        return {"checked": len(open_tickets)}
    finally:
        db.close()
