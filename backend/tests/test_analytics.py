# backend/tests/test_analytics.py
"""Tests for analytics endpoints — ticket metrics, SLA, agent performance, revenue."""
import pytest
from datetime import datetime, timedelta, timezone


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def ticket_data(db, client_org, staff_user, service):
    """Create a set of tickets for analytics tests."""
    from app.models.ticket import Ticket

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tickets = [
        Ticket(
            org_id=client_org.id,
            service_id=service.id,
            subject="Open ticket",
            status="Open",
            priority="High",
            ticket_type="Bug",
            source="portal",
            raised_by_email="c@test.com",
            created_at=now - timedelta(days=5),
        ),
        Ticket(
            org_id=client_org.id,
            service_id=service.id,
            subject="Resolved ticket",
            status="Resolved",
            priority="Low",
            ticket_type="Question",
            source="portal",
            raised_by_email="c@test.com",
            assignee_id=staff_user.id,
            created_at=now - timedelta(days=10),
            resolved_at=now - timedelta(days=8),
            resolution_by=now - timedelta(days=7),
        ),
        Ticket(
            org_id=client_org.id,
            service_id=service.id,
            subject="Breached ticket",
            status="Open",
            priority="Urgent",
            ticket_type="Incident",
            source="portal",
            raised_by_email="c@test.com",
            assignee_id=staff_user.id,
            created_at=now - timedelta(days=20),
            resolution_by=now - timedelta(days=15),
        ),
    ]
    for t in tickets:
        db.add(t)
    db.commit()
    for t in tickets:
        db.refresh(t)
    return tickets


@pytest.fixture
def invoice_data(db, client_org):
    """Create invoices for revenue analytics tests."""
    from app.models.invoice import Invoice
    from datetime import date

    today = date.today()
    invoices = [
        Invoice(
            invoice_number="INV-TEST-001",
            org_id=client_org.id,
            status="paid",
            issue_date=today - timedelta(days=40),
            due_date=today - timedelta(days=10),
            subtotal=1000000,
            tax_rate=10,
            tax_amount=100000,
            total=1100000,
        ),
        Invoice(
            invoice_number="INV-TEST-002",
            org_id=client_org.id,
            status="overdue",
            issue_date=today - timedelta(days=20),
            due_date=today - timedelta(days=5),
            subtotal=500000,
            tax_rate=10,
            tax_amount=50000,
            total=550000,
        ),
        Invoice(
            invoice_number="INV-TEST-003",
            org_id=client_org.id,
            status="sent",
            issue_date=today,
            due_date=today + timedelta(days=30),
            subtotal=200000,
            tax_rate=10,
            tax_amount=20000,
            total=220000,
        ),
    ]
    for inv in invoices:
        db.add(inv)
    db.commit()
    return invoices


# ── /api/analytics/tickets ────────────────────────────────────────────────────

def test_ticket_analytics_admin(client, admin_token, ticket_data):
    r = client.get("/api/analytics/tickets", headers=auth(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert data["total"] == 3
    assert "by_status" in data
    assert "by_priority" in data
    assert "by_type" in data
    assert "daily_trend" in data
    assert "avg_resolution_hours" in data


def test_ticket_analytics_staff_scoped(client, staff_token, staff_assignment, ticket_data):
    """Staff sees tickets from their assigned org."""
    r = client.get("/api/analytics/tickets", headers=auth(staff_token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3


def test_ticket_analytics_customer_forbidden(client, customer_token):
    r = client.get("/api/analytics/tickets", headers=auth(customer_token))
    assert r.status_code == 403


def test_ticket_analytics_unauthenticated(client):
    r = client.get("/api/analytics/tickets")
    assert r.status_code == 401


def test_ticket_analytics_org_filter(client, admin_token, ticket_data, second_client_org, db, service):
    """Filter by org_id returns only that org's tickets."""
    from app.models.ticket import Ticket
    other_ticket = Ticket(
        org_id=second_client_org.id,
        service_id=service.id,
        subject="Other org ticket",
        status="Open",
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by_email="other@test.com",
    )
    db.add(other_ticket)
    db.commit()

    r = client.get(
        f"/api/analytics/tickets?org_id={second_client_org.id}",
        headers=auth(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["total"] == 1


# ── /api/analytics/sla ────────────────────────────────────────────────────────

def test_sla_analytics_basic(client, admin_token, ticket_data):
    r = client.get("/api/analytics/sla", headers=auth(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "total_tickets" in data
    assert "sla_met" in data
    assert "sla_breached" in data
    assert "compliance_rate" in data
    assert "by_priority" in data
    # 2 tickets have resolution_by set; 1 met (resolved before deadline), 1 breached
    assert data["total_tickets"] == 2
    assert data["sla_met"] == 1
    assert data["sla_breached"] == 1


def test_sla_analytics_staff_forbidden_without_assignment(client, staff_token):
    """Staff with no assignments sees 0 tickets (not an error)."""
    r = client.get("/api/analytics/sla", headers=auth(staff_token))
    assert r.status_code == 200
    assert r.json()["total_tickets"] == 0


def test_sla_analytics_customer_forbidden(client, customer_token):
    r = client.get("/api/analytics/sla", headers=auth(customer_token))
    assert r.status_code == 403


# ── /api/analytics/agents ────────────────────────────────────────────────────

def test_agent_analytics_admin(client, admin_token, ticket_data, staff_user):
    r = client.get("/api/analytics/agents", headers=auth(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "agents" in data
    agents = {a["user_id"]: a for a in data["agents"]}
    assert staff_user.id in agents
    entry = agents[staff_user.id]
    assert entry["tickets_assigned"] == 2
    assert entry["tickets_resolved"] == 1


def test_agent_analytics_staff_forbidden(client, staff_token):
    r = client.get("/api/analytics/agents", headers=auth(staff_token))
    assert r.status_code == 403


def test_agent_analytics_customer_forbidden(client, customer_token):
    r = client.get("/api/analytics/agents", headers=auth(customer_token))
    assert r.status_code == 403


# ── /api/analytics/revenue ────────────────────────────────────────────────────

def test_revenue_analytics_admin(client, admin_token, invoice_data):
    r = client.get("/api/analytics/revenue", headers=auth(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "total_invoiced" in data
    assert "total_paid" in data
    assert "total_overdue" in data
    assert "by_month" in data
    assert "by_org" in data
    assert abs(data["total_invoiced"] - 1870000) < 1
    assert abs(data["total_paid"] - 1100000) < 1
    assert abs(data["total_overdue"] - 550000) < 1


def test_revenue_analytics_staff_forbidden(client, staff_token):
    r = client.get("/api/analytics/revenue", headers=auth(staff_token))
    assert r.status_code == 403


def test_revenue_analytics_customer_forbidden(client, customer_token):
    r = client.get("/api/analytics/revenue", headers=auth(customer_token))
    assert r.status_code == 403


def test_revenue_analytics_org_filter(client, admin_token, invoice_data, client_org, second_client_org, db):
    """Org filter restricts revenue to that org only."""
    from app.models.invoice import Invoice
    from datetime import date

    inv = Invoice(
        invoice_number="INV-TEST-999",
        org_id=second_client_org.id,
        status="paid",
        issue_date=date.today(),
        due_date=date.today(),
        subtotal=9000000,
        tax_rate=10,
        tax_amount=900000,
        total=9900000,
    )
    db.add(inv)
    db.commit()

    r = client.get(
        f"/api/analytics/revenue?org_id={client_org.id}",
        headers=auth(admin_token),
    )
    assert r.status_code == 200
    data = r.json()
    assert abs(data["total_invoiced"] - 1870000) < 1


# ── New: exact-value and scoping tests ────────────────────────────────────────

def test_ticket_by_status_exact_counts(client, admin_token, ticket_data):
    """by_status uses Title Case enum values and counts are correct."""
    r = client.get("/api/analytics/tickets", headers=auth(admin_token))
    assert r.status_code == 200
    by_status = r.json()["by_status"]
    # ticket_data: 2 Open, 1 Resolved (exact enum strings from model)
    assert by_status.get("Open", 0) == 2
    assert by_status.get("Resolved", 0) == 1
    assert "open" not in by_status      # key must NOT be lowercase
    assert "resolved" not in by_status  # key must NOT be lowercase


def test_ticket_by_priority_exact_counts(client, admin_token, ticket_data):
    """by_priority counts match seeded data."""
    r = client.get("/api/analytics/tickets", headers=auth(admin_token))
    assert r.status_code == 200
    by_priority = r.json()["by_priority"]
    assert by_priority.get("High", 0) == 1
    assert by_priority.get("Low", 0) == 1
    assert by_priority.get("Urgent", 0) == 1


def test_ticket_avg_resolution_correct(client, admin_token, ticket_data):
    """avg_resolution_hours matches the seeded resolved ticket (2 days = 48 h)."""
    r = client.get("/api/analytics/tickets", headers=auth(admin_token))
    assert r.status_code == 200
    avg = r.json()["avg_resolution_hours"]
    assert avg is not None
    # resolved ticket: created 10 days ago, resolved 8 days ago → 2 days = 48 h
    assert abs(avg - 48.0) < 1.0  # allow 1 h tolerance for timing jitter


def test_ticket_daily_trend_has_entries(client, admin_token, ticket_data):
    """daily_trend returns list of {date, count} dicts."""
    r = client.get("/api/analytics/tickets", headers=auth(admin_token))
    assert r.status_code == 200
    trend = r.json()["daily_trend"]
    assert isinstance(trend, list)
    assert len(trend) >= 1
    assert all("date" in entry and "count" in entry for entry in trend)
    total_from_trend = sum(e["count"] for e in trend)
    assert total_from_trend == 3


def test_sla_by_sla_state_returned(client, admin_token, ticket_data):
    """SLA endpoint returns by_sla_state dict keyed by enum values."""
    r = client.get("/api/analytics/sla", headers=auth(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert "by_sla_state" in data
    assert "sla_state_compliance_rate" in data
    assert "sla_state_breached" in data
    # All test tickets default sla_state="green"
    by_sla_state = data["by_sla_state"]
    assert by_sla_state.get("green", 0) == 3
    assert data["sla_state_breached"] == 0
    assert data["sla_state_compliance_rate"] == 100.0


def test_sla_by_sla_state_breached_ticket(client, admin_token, db, client_org, service):
    """A ticket with sla_state='breached' is counted correctly."""
    from app.models.ticket import Ticket

    t = Ticket(
        org_id=client_org.id,
        service_id=service.id,
        subject="SLA breached",
        status="Open",
        priority="Urgent",
        ticket_type="Incident",
        source="portal",
        raised_by_email="b@test.com",
        sla_state="breached",
    )
    db.add(t)
    db.commit()

    r = client.get("/api/analytics/sla", headers=auth(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert data["by_sla_state"].get("breached", 0) >= 1
    assert data["sla_state_breached"] >= 1
    assert data["sla_state_compliance_rate"] < 100.0


def test_ticket_analytics_staff_cross_org_blocked(
    client, staff_token, second_client_org, db, service
):
    """Staff not assigned to second_client_org cannot see its tickets."""
    from app.models.ticket import Ticket

    t = Ticket(
        org_id=second_client_org.id,
        service_id=service.id,
        subject="Org2 ticket",
        status="Open",
        priority="Low",
        ticket_type="Question",
        source="portal",
        raised_by_email="x@test.com",
    )
    db.add(t)
    db.commit()

    r = client.get("/api/analytics/tickets", headers=auth(staff_token))
    assert r.status_code == 200
    # staff_user has no assignment → sees 0 tickets (not 500, not 403)
    assert r.json()["total"] == 0


def test_ticket_analytics_empty_returns_zeros(client, admin_token):
    """No tickets → total=0, by_status={}, daily_trend=[], avg=None. No 500."""
    r = client.get(
        "/api/analytics/tickets?from_date=2000-01-01&to_date=2000-01-02",
        headers=auth(admin_token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["by_status"] == {}
    assert data["daily_trend"] == []
    assert data["avg_resolution_hours"] is None


def test_sla_analytics_empty_returns_zeros(client, admin_token):
    """No tickets with deadline → total_tickets=0, compliance_rate=0.0. No 500."""
    r = client.get(
        "/api/analytics/sla?from_date=2000-01-01&to_date=2000-01-02",
        headers=auth(admin_token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_tickets"] == 0
    assert data["compliance_rate"] == 0.0
    assert data["by_sla_state"] == {}
    assert data["sla_state_compliance_rate"] == 0.0


def test_agent_tickets_open_field(client, admin_token, ticket_data, staff_user):
    """Agent entry includes tickets_open for open-status tickets."""
    r = client.get("/api/analytics/agents", headers=auth(admin_token))
    assert r.status_code == 200
    agents = {a["user_id"]: a for a in r.json()["agents"]}
    entry = agents[staff_user.id]
    assert "tickets_open" in entry
    # Breached ticket (status=Open) is assigned to staff_user → open=1
    assert entry["tickets_open"] == 1
    assert entry["tickets_resolved"] == 1
