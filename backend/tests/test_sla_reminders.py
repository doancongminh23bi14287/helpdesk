from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.redis_client import redis_client
from app.models.notification import Notification
from app.models.ticket import Ticket
from app.tasks.sla_checker import check_sla
from tests.conftest import TestingSessionLocal


def _naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _red_ticket(db, client_org, staff_user):
    now = _naive_now()
    ticket = Ticket(
        org_id=client_org.id,
        subject="SLA reminder sequence",
        status="Open",
        priority="High",
        assignee_id=staff_user.id,
        sla_state="green",
        created_at=now - timedelta(hours=10),
        resolution_by=now + timedelta(hours=1),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def _notification_count(db, ticket_id, user_id):
    db.commit()
    db.expire_all()
    return db.query(Notification).filter(
        Notification.ref_ticket_id == ticket_id,
        Notification.user_id == user_id,
        Notification.type == "sla",
    ).count()


def test_sla_transition_and_hourly_reminder_sequence(
    db, admin_user, staff_user, client_org
):
    ticket = _red_ticket(db, client_org, staff_user)

    with patch("app.tasks.sla_checker.SessionLocal", TestingSessionLocal):
        first = check_sla()
        assert first["entering_red"] == 1
        assert _notification_count(db, ticket.id, staff_user.id) == 1

        second = check_sla()
        assert second["reminders"] == 0
        assert _notification_count(db, ticket.id, staff_user.id) == 1

        redis_client.delete(
            f"sla:alert:{ticket.id}:red:assignee:{staff_user.id}"
        )
        third = check_sla()
        assert third["reminders"] == 1
        assert _notification_count(db, ticket.id, staff_user.id) == 2

        db.query(Ticket).filter(Ticket.id == ticket.id).update({
            Ticket.resolution_by: _naive_now() - timedelta(minutes=1),
        })
        db.commit()
        breached = check_sla()
        assert breached["entering_breached"] == 1
        assert _notification_count(db, ticket.id, admin_user.id) == 1

        within_ttl = check_sla()
        assert within_ttl["reminders"] == 0
        assert _notification_count(db, ticket.id, admin_user.id) == 1

        redis_client.delete(
            f"sla:alert:{ticket.id}:breached:admin:{admin_user.id}"
        )
        after_ttl = check_sla()
        assert after_ttl["reminders"] >= 1
        assert _notification_count(db, ticket.id, admin_user.id) == 2


def test_redis_failure_keeps_transition_alert_and_suppresses_repeat(
    db, staff_user, client_org
):
    ticket = _red_ticket(db, client_org, staff_user)

    with patch("app.tasks.sla_checker.SessionLocal", TestingSessionLocal), patch(
        "app.tasks.sla_checker.redis_client"
    ) as unavailable:
        unavailable.setex.side_effect = ConnectionError("redis unavailable")
        unavailable.set.side_effect = ConnectionError("redis unavailable")

        first = check_sla()
        assert first["entering_red"] == 1
        assert _notification_count(db, ticket.id, staff_user.id) == 1

        second = check_sla()
        assert second["reminders"] == 0
        assert _notification_count(db, ticket.id, staff_user.id) == 1
