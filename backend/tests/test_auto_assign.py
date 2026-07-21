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


# ── test_assign_endpoint_admin_can_assign_eligible_staff ──────────────────────

def test_assign_endpoint_admin_can_assign_eligible_staff(
    client, db, admin_token, staff_user, staff_assignment,
    client_org, service, customer_user,
):
    """Admin can assign an active staff member eligible for the ticket org."""
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

def test_recent_login_is_not_treated_as_online_presence(
    db, admin_user, staff_user, staff_assignment, client_org
):
    from app.models.ticket import Ticket
    from app.services.auto_assign import score_breakdown

    staff_user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    ticket = Ticket(
        org_id=client_org.id,
        subject="Presence must not come from login",
        status="Open",
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by=admin_user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    score = next(
        item for item in score_breakdown(ticket, db)
        if item["user_id"] == staff_user.id
    )
    assert score["online"] == 0
    assert score["online_score"] == 0


def test_project_member_restricts_auto_assignment(
    client, db, admin_user, customer_token, client_org, provider_org, service, staff_assignment
):
    from app.models.user import User
    from app.core.security import hash_password
    from app.models.project import Project, ProjectMember
    from app.models.team import StaffOrgAssignment

    staff2 = User(
        org_id=provider_org.id,
        email="staff2-project@test.com",
        password_hash=hash_password("s"),
        full_name="Staff Project",
        role="staff",
        is_active=True,
    )
    db.add(staff2)
    db.commit()
    db.refresh(staff2)
    db.add(StaffOrgAssignment(user_id=staff2.id, org_id=client_org.id))
    db.commit()

    project = Project(
        org_id=client_org.id,
        name="Member Only Project",
        project_type="seo",
        status="open",
        visibility="customer_visible",
        created_by=admin_user.id,
        progress_percent=0,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    db.add(ProjectMember(project_id=project.id, user_id=staff2.id, role="staff", added_by=admin_user.id))
    db.commit()

    response = client.post(
        "/api/tickets",
        json={
            "org_id": client_org.id,
            "service_id": service.id,
            "project_id": project.id,
            "subject": "Project member assignment test",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project.id
    assert data["assignee_id"] == staff2.id


def test_workload_sums_active_tickets_and_tasks_and_excludes_terminal(
    db, admin_user, staff_user, staff_assignment, client_org
):
    from app.models.project import Project, ProjectTask, TaskAssignee
    from app.models.ticket import Ticket, TicketAssignee
    from app.services.auto_assign import score_breakdown

    project = Project(
        org_id=client_org.id,
        name="Combined workload",
        project_type="seo",
        status="open",
        visibility="customer_visible",
        created_by=admin_user.id,
        progress_percent=0,
    )
    db.add(project)
    db.flush()

    active_ticket = Ticket(
        org_id=client_org.id,
        subject="Active assigned work",
        status="Open",
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by=admin_user.id,
    )
    closed_ticket = Ticket(
        org_id=client_org.id,
        subject="Closed assigned work",
        status="Closed",
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by=admin_user.id,
    )
    target = Ticket(
        org_id=client_org.id,
        subject="Target",
        status="Open",
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by=admin_user.id,
    )
    db.add_all([active_ticket, closed_ticket, target])
    db.flush()
    db.add_all([
        TicketAssignee(ticket_id=active_ticket.id, user_id=staff_user.id, is_primary=True),
        TicketAssignee(ticket_id=closed_ticket.id, user_id=staff_user.id, is_primary=True),
    ])

    active_task = ProjectTask(
        project_id=project.id,
        title="Active task",
        status="working",
        priority="medium",
        task_type="other",
        created_by=admin_user.id,
    )
    completed_task = ProjectTask(
        project_id=project.id,
        title="Completed task",
        status="completed",
        priority="medium",
        task_type="other",
        created_by=admin_user.id,
    )
    db.add_all([active_task, completed_task])
    db.flush()
    db.add_all([
        TaskAssignee(task_id=active_task.id, user_id=staff_user.id, is_primary=True),
        TaskAssignee(task_id=completed_task.id, user_id=staff_user.id, is_primary=True),
    ])
    db.commit()

    score = next(
        row for row in score_breakdown(target, db)
        if row["user_id"] == staff_user.id
    )
    assert score["active_ticket_count"] == 1
    assert score["active_task_count"] == 1
    assert score["load_units"] == 2


def test_heartbeat_presence_awards_twenty_points(
    db, admin_user, staff_user, staff_assignment, client_org
):
    from app.core.redis_client import redis_client
    from app.models.ticket import Ticket
    from app.services.auto_assign import score_breakdown

    target = Ticket(
        org_id=client_org.id,
        subject="Online target",
        status="Open",
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by=admin_user.id,
    )
    db.add(target)
    db.commit()
    redis_client.setex(f"presence:user:{staff_user.id}", 90, "test")

    score = next(
        row for row in score_breakdown(target, db)
        if row["user_id"] == staff_user.id
    )
    assert score["online"] == 1
    assert score["online_score"] == 20


def test_tie_break_prefers_never_assigned_then_stable_user_id():
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.services.auto_assign import _do_find_best_assignee

    tied = [
        {"user_id": 9, "total_score": 50, "last_assigned_at": None},
        {"user_id": 4, "total_score": 50, "last_assigned_at": None},
        {
            "user_id": 1,
            "total_score": 50,
            "last_assigned_at": datetime.now(timezone.utc).replace(tzinfo=None),
        },
    ]
    with patch("app.services.auto_assign._compute_scores", return_value=tied):
        winner = _do_find_best_assignee(SimpleNamespace(id=99), None)

    assert winner == 4


def test_held_assignment_lock_defers_selection():
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.services.auto_assign import find_best_assignee

    with patch("app.services.auto_assign.redis_client") as redis_mock, patch(
        "app.services.auto_assign.time.sleep"
    ), patch("app.services.auto_assign._do_find_best_assignee") as select:
        redis_mock.set.return_value = False
        result = find_best_assignee(SimpleNamespace(org_id=8), None)

    assert result is None
    assert redis_mock.set.call_count == 2
    select.assert_not_called()


def test_assignment_lock_release_is_token_owned():
    from unittest.mock import patch
    from app.services.auto_assign import _release_assignment_lock

    with patch("app.services.auto_assign.redis_client") as redis_mock:
        _release_assignment_lock("assignment:org:3", "owner-token")

    redis_mock.eval.assert_called_once()
    args = redis_mock.eval.call_args.args
    assert args[-2:] == ("assignment:org:3", "owner-token")


def test_redis_lock_failure_leaves_ticket_unassigned():
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.services.auto_assign import find_best_assignee

    with patch("app.services.auto_assign.redis_client") as redis_mock, patch(
        "app.services.auto_assign._do_find_best_assignee", return_value=17
    ) as select:
        redis_mock.set.side_effect = ConnectionError("redis unavailable")
        result = find_best_assignee(SimpleNamespace(org_id=8), object())

    assert result is None
    select.assert_not_called()

def test_transaction_assignment_lock_is_held_until_explicit_release():
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.services.auto_assign import (
        find_best_assignee_for_transaction,
        release_transaction_assignment_lock,
    )

    db = SimpleNamespace(info={})
    ticket = SimpleNamespace(org_id=8)
    with patch("app.services.auto_assign.redis_client") as redis_mock, patch(
        "app.services.auto_assign._do_find_best_assignee", return_value=17
    ):
        redis_mock.set.return_value = True
        assert find_best_assignee_for_transaction(ticket, db) == 17
        assert "assignment_lock" in db.info
        release_transaction_assignment_lock(db)

    redis_mock.eval.assert_called_once()
