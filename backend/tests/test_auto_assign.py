# backend/tests/test_auto_assign.py
"""Phase 3 auto-assignment tests."""
import pytest
from datetime import datetime, timezone, timedelta


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_ticket_via_api(client, token, org_id, service_id, subject="Test ticket"):
    r = client.post(
        "/api/tickets",
        json={
            "org_id": org_id,
            "service_id": service_id,
            "subject": subject,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return r


# ── test_auto_assign_picks_lowest_workload ────────────────────────────────────

def test_auto_assign_picks_lowest_workload(
    client, db, admin_token, admin_user, customer_token,
    provider_org, client_org, staff_user, staff_assignment, service,
):
    """
    staff_user (staff1) has 3 active project tasks; staff2 has 0.
    New ticket via API should be auto-assigned to staff2.
    """
    from app.models.user import User
    from app.models.team import StaffOrgAssignment
    from app.models.ticket import TicketActivity
    from app.models.project import Project, ProjectTask
    from app.core.security import hash_password

    # Create second staff user
    staff2 = User(
        org_id=provider_org.id,
        email="staff2t@test.com",
        password_hash=hash_password("s"),
        full_name="Staff Two",
        role="staff",
        is_active=True,
    )
    db.add(staff2)
    db.commit()
    db.refresh(staff2)

    # Assign staff2 to client_org
    assn2 = StaffOrgAssignment(user_id=staff2.id, org_id=client_org.id)
    db.add(assn2)
    db.commit()

    # Give staff_user 3 active project tasks (new workload metric)
    project = Project(
        org_id=client_org.id,
        name="Workload Test Project",
        project_type="seo",
        status="open",
        visibility="customer_visible",
        created_by=admin_user.id,
        progress_percent=0,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    for i in range(3):
        db.add(ProjectTask(
            project_id=project.id,
            title=f"Task {i}",
            task_type="other",
            assignee_id=staff_user.id,
            status="open",
            priority="medium",
            is_client_visible=False,
            created_by=admin_user.id,
        ))
    db.commit()

    # Create a new ticket via API (customer creates it)
    r = _create_ticket_via_api(client, customer_token, client_org.id, service.id, "New ticket needs agent")
    assert r.status_code == 201, r.text
    data = r.json()

    # staff2 has lower workload (0 open tickets vs staff1's 3)
    assert data["assignee_id"] == staff2.id, (
        f"Expected assignee_id={staff2.id} (staff2) but got {data['assignee_id']}"
    )

    # Verify auto_assigned activity exists
    from app.models.ticket import TicketActivity as TA
    new_ticket_id = data["id"]
    activity = (
        db.query(TA)
        .filter(
            TA.ticket_id == new_ticket_id,
            TA.action == "auto_assigned",
        )
        .first()
    )
    assert activity is not None, "Expected an auto_assigned activity"
    assert activity.to_value == str(staff2.id)


# ── test_auto_assign_no_staff_leaves_unassigned ───────────────────────────────

def test_auto_assign_no_staff_leaves_unassigned(
    client, db, customer_token, client_org, service,
):
    """No staff assigned to client_org — ticket remains unassigned."""
    # NOTE: we intentionally do NOT use staff_assignment fixture, so no staff for client_org
    r = _create_ticket_via_api(client, customer_token, client_org.id, service.id, "Unassigned ticket")
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["assignee_id"] is None


# ── test_assign_endpoint_admin_can_assign_anyone ──────────────────────────────

def test_assign_endpoint_admin_can_assign_anyone(
    client, db, admin_token, staff_user, staff_assignment,
    client_org, service, customer_user,
):
    """Admin can assign a ticket to any staff user via POST /assign."""
    # Create a ticket (no auto-assign since staff is in org but that's OK)
    r = _create_ticket_via_api(client, admin_token, client_org.id, service.id, "Admin assign test")
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    # Admin assigns to staff_user
    r2 = client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": staff_user.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["assignee_id"] == staff_user.id


# ── test_assign_endpoint_staff_can_self_assign ────────────────────────────────

def test_assign_endpoint_staff_can_self_assign(
    client, db, staff_token, staff_user, staff_assignment,
    client_org, service, customer_token,
):
    """Staff can self-assign a ticket."""
    # Customer creates ticket
    r = _create_ticket_via_api(client, customer_token, client_org.id, service.id, "Self-assign test")
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    r2 = client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": staff_user.id},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["assignee_id"] == staff_user.id


# ── test_assign_endpoint_staff_cannot_assign_others ──────────────────────────

def test_assign_endpoint_staff_cannot_assign_others(
    client, db, staff_token, staff_user, staff_assignment,
    client_org, service, admin_user, customer_token,
):
    """Staff cannot assign a ticket to someone else — 403."""
    # Customer creates ticket
    r = _create_ticket_via_api(client, customer_token, client_org.id, service.id, "Assign-other test")
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    r2 = client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": admin_user.id},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r2.status_code == 403, r2.text


# ── test_assign_endpoint_customer_forbidden ───────────────────────────────────

def test_assign_endpoint_customer_forbidden(
    client, db, customer_token, staff_assignment,
    client_org, service, staff_user,
):
    """Customers cannot use the assign endpoint — 403."""
    # Create a ticket first
    r = _create_ticket_via_api(client, customer_token, client_org.id, service.id, "Customer assign test")
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    r2 = client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": staff_user.id},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r2.status_code == 403, r2.text


# ── test_assignment_score_endpoint ────────────────────────────────────────────

def test_assignment_score_endpoint(
    client, db, admin_token, staff_user, staff_assignment,
    client_org, service, customer_token,
):
    """Admin can GET /assignment-score for a ticket; returns list with score fields."""
    # Customer creates ticket
    r = _create_ticket_via_api(client, customer_token, client_org.id, service.id, "Score endpoint test")
    assert r.status_code == 201, r.text
    ticket_id = r.json()["id"]

    r2 = client.get(
        f"/api/tickets/{ticket_id}/assignment-score",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert isinstance(data, list)
    # staff_user is assigned to client_org, so they appear in the list
    assert len(data) >= 1
    first = data[0]
    assert "total_score" in first
    assert "workload_score" in first
    assert "skill_score" in first
    assert "online_score" in first
