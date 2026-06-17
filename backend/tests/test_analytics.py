# backend/tests/test_analytics.py
"""Tests for Phase 6 analytics endpoints."""
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
