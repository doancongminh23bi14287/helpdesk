# backend/tests/test_sla.py
"""Phase 3 — SLA monitoring tests (TDD: tests first)."""
import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch


# ── Helper ────────────────────────────────────────────────────────────────────

def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_sla_policies(db):
    """Seed SLA policies into the test DB."""
    from app.models.sla import SlaPolicy
    policies = [
        SlaPolicy(priority="Urgent", response_hours=0.25, resolution_hours=2),
        SlaPolicy(priority="High", response_hours=1, resolution_hours=8),
        SlaPolicy(priority="Medium", response_hours=4, resolution_hours=24),
        SlaPolicy(priority="Low", response_hours=8, resolution_hours=72),
    ]
    for p in policies:
        existing = db.query(SlaPolicy).filter(SlaPolicy.priority == p.priority).first()
        if not existing:
            db.add(p)
    db.commit()


def _create_ticket_via_api(client, token, org_id, service_id, subject="Test ticket", priority="High"):
    payload = {
        "org_id": org_id,
        "service_id": service_id,
        "subject": subject,
        "priority": priority,
    }
    return client.post("/api/tickets", json=payload, headers=auth(token))


# ── Test 1: SLA timestamps computed on ticket create ─────────────────────────

def test_sla_timestamps_computed_on_ticket_create(
    client, db, admin_token, client_org, service
):
    _seed_sla_policies(db)

    r = _create_ticket_via_api(client, admin_token, client_org.id, service.id, priority="High")
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    r_sla = client.get(f"/api/tickets/{ticket_id}/sla", headers=auth(admin_token))
    assert r_sla.status_code == 200, r_sla.text
    data = r_sla.json()

    assert data["response_by"] is not None, "response_by should be set"
    assert data["resolution_by"] is not None, "resolution_by should be set"
    assert data["hours_remaining"] is not None
    assert data["hours_remaining"] > 0, "ticket should not be breached immediately"
    assert data["state"] == "green"


# ── Test 2: SLA state thresholds (pure unit test, no DB) ─────────────────────

def test_sla_state_green_amber_red_breached_thresholds():
    from app.services.sla_monitor import get_sla_status

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Green: 12h window, 10h left → ~83% remaining
    t_green = SimpleNamespace(
        created_at=now - timedelta(hours=2),
        resolution_by=now + timedelta(hours=10),
        response_by=None,
        resolved_at=None,
        closed_at=None,
        status="Open",
    )
    result = get_sla_status(t_green)
    assert result["state"] == "green", f"Expected green, got {result['state']}"

    # Amber: 12h window, 3h left → 25% remaining
    t_amber = SimpleNamespace(
        created_at=now - timedelta(hours=9),
        resolution_by=now + timedelta(hours=3),
        response_by=None,
        resolved_at=None,
        closed_at=None,
        status="Open",
    )
    result = get_sla_status(t_amber)
    assert result["state"] == "amber", f"Expected amber, got {result['state']}"

    # Red: 12h window, 1h left → ~8% remaining
    t_red = SimpleNamespace(
        created_at=now - timedelta(hours=11),
        resolution_by=now + timedelta(hours=1),
        response_by=None,
        resolved_at=None,
        closed_at=None,
        status="Open",
    )
    result = get_sla_status(t_red)
    assert result["state"] == "red", f"Expected red, got {result['state']}"

    # Breached: resolution_by in the past
    t_breached = SimpleNamespace(
        created_at=now - timedelta(hours=13),
        resolution_by=now - timedelta(hours=1),
        response_by=None,
        resolved_at=None,
        closed_at=None,
        status="Open",
    )
    result = get_sla_status(t_breached)
    assert result["state"] == "breached", f"Expected breached, got {result['state']}"


# ── Test 3: SLA checker creates breach notification ───────────────────────────

def test_sla_checker_creates_breach_notification(db, admin_user, client_org):
    from app.models.ticket import Ticket
    from app.models.notification import Notification
    from app.models.sla import SlaPolicy

    # Seed SLA policy
    policy = db.query(SlaPolicy).filter(SlaPolicy.priority == "Medium").first()
    if not policy:
        policy = SlaPolicy(priority="Medium", response_hours=4, resolution_hours=24)
        db.add(policy)

    # Create a ticket with breached SLA (resolution_by in the past)
    breached_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    ticket = Ticket(
        org_id=client_org.id,
        subject="Breached SLA ticket",
        status="Open",
        priority="Medium",
        resolution_by=breached_time,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    from app.tasks.sla_checker import check_sla
    from tests.conftest import TestingSessionLocal
    with patch("app.tasks.sla_checker.SessionLocal", TestingSessionLocal):
        check_sla()

    # Commit and expire to break REPEATABLE READ snapshot, then re-query
    db.commit()
    db.expire_all()
    notif = db.query(Notification).filter(
        Notification.ref_ticket_id == ticket.id,
        Notification.type == "sla",
        Notification.user_id == admin_user.id,
    ).first()
    assert notif is not None, "Expected a breach notification for admin"
    assert "BREACHED" in notif.title or "breached" in notif.title.lower()


# ── Test 4: SLA endpoint returns state ───────────────────────────────────────

def test_sla_endpoint_returns_state(
    client, db, admin_token, client_org, service
):
    _seed_sla_policies(db)

    r = _create_ticket_via_api(client, admin_token, client_org.id, service.id)
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    r_sla = client.get(f"/api/tickets/{ticket_id}/sla", headers=auth(admin_token))
    assert r_sla.status_code == 200, r_sla.text
    data = r_sla.json()

    assert "state" in data
    assert "resolution_by" in data


# ── Test 5: SLA dedup — no double notify ─────────────────────────────────────

def test_sla_dedup_no_double_notify(db, admin_user, client_org):
    from app.models.ticket import Ticket
    from app.models.notification import Notification
    from app.models.sla import SlaPolicy

    # Seed SLA policy
    policy = db.query(SlaPolicy).filter(SlaPolicy.priority == "High").first()
    if not policy:
        policy = SlaPolicy(priority="High", response_hours=1, resolution_hours=8)
        db.add(policy)

    # Create a ticket with breached SLA
    breached_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    ticket = Ticket(
        org_id=client_org.id,
        subject="Dedup SLA ticket",
        status="Open",
        priority="High",
        resolution_by=breached_time,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=10),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    from app.tasks.sla_checker import check_sla
    from tests.conftest import TestingSessionLocal
    with patch("app.tasks.sla_checker.SessionLocal", TestingSessionLocal):
        check_sla()
        check_sla()

    # Commit and expire to break REPEATABLE READ snapshot, then re-query
    db.commit()
    db.expire_all()
    notifs = db.query(Notification).filter(
        Notification.ref_ticket_id == ticket.id,
        Notification.type == "sla",
        Notification.user_id == admin_user.id,
    ).all()
    assert len(notifs) == 1, f"Expected 1 notification (dedup), got {len(notifs)}"
