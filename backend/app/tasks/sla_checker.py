# backend/app/tasks/sla_checker.py
from app.tasks.celery_app import celery_app
from app.database import SessionLocal


@celery_app.task(name="app.tasks.sla_checker.check_sla")
def check_sla():
    """
    Check all open tickets. Update sla_state. Create notifications for red/breached.
    Dedup: don't re-notify same ticket+state within 1 hour.
    """
    db = SessionLocal()
    try:
        from app.models.ticket import Ticket
        from app.models.notification import Notification
        from app.models.user import User
        from app.services.sla_monitor import get_sla_status
        from app.services.notify import create_notification
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func

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
                ticket.sla_state = new_state

            # Notify on red or breached — dedup within 1 hour
            if new_state in ("red", "breached"):
                one_hour_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
                # Check if a notification for this ticket+state was already sent in last 1h
                already_notified = db.query(Notification).filter(
                    Notification.ref_ticket_id == ticket.id,
                    Notification.type == "sla",
                    Notification.content.like(f"[sla:{new_state}]%"),
                    Notification.created_at >= one_hour_ago,
                ).first()

                if not already_notified:
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

        db.commit()
        return {"checked": len(open_tickets)}
    finally:
        db.close()
