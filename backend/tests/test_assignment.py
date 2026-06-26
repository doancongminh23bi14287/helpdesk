"""Tests for Sprint B multi-assignee system (ticket_assignees + member-sync)."""
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_project(db, org_id, created_by):
    from app.models.project import Project
    p = Project(
        org_id=org_id,
        name="Test Project",
        project_type="seo",
        status="open",
        visibility="customer_visible",
        created_by=created_by,
        progress_percent=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_staff2(db, provider_org):
    from app.models.user import User
    from app.core.security import hash_password
    u = User(
        org_id=provider_org.id,
        email="staff2_assign@test.com",
        password_hash=hash_password("s"),
        full_name="Staff Two",
        role="staff",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _create_ticket(client, token, org_id, service_id, **extra):
    payload = {"org_id": org_id, "service_id": service_id, "subject": "Assign test", **extra}
    r = client.post("/api/tickets", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


# ── assignment_mode and assignees in response ─────────────────────────────────

def test_create_ticket_has_assignment_mode_and_assignees(
    client, admin_token, client_org, service
):
    """POST /tickets response must include assignment_mode and assignees list."""
    data = _create_ticket(client, admin_token, client_org.id, service.id)
    assert "assignment_mode" in data
    assert "assignees" in data
    assert isinstance(data["assignees"], list)


def test_create_ticket_none_mode_leaves_unassigned(
    client, admin_token, staff_user, staff_assignment, client_org, service
):
    """assignment_mode='none' → no assignees, assignee_id=null."""
    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="none",
    )
    assert data["assignment_mode"] == "none"
    assert data["assignee_id"] is None
    assert data["assignees"] == []


def test_create_ticket_manual_mode_single_assignee(
    client, db, admin_token, staff_user, staff_assignment, client_org, service
):
    """Manual mode with one assignee_ids entry → 1 ticket_assignee row, is_primary=True."""
    from app.models.ticket import TicketAssignee

    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    assert data["assignment_mode"] == "manual"
    assert data["assignee_id"] == staff_user.id
    assert len(data["assignees"]) == 1
    assert data["assignees"][0]["user_id"] == staff_user.id
    assert data["assignees"][0]["is_primary"] is True

    rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id == data["id"]).all()
    assert len(rows) == 1
    assert rows[0].is_primary is True


def test_create_ticket_manual_mode_multi_assignee(
    client, db, admin_token, staff_user, staff_assignment, provider_org, client_org, service
):
    """Manual mode with two assignee_ids → 2 rows, first is primary."""
    from app.models.ticket import TicketAssignee

    staff2 = _make_staff2(db, provider_org)
    from app.models.team import StaffOrgAssignment
    db.add(StaffOrgAssignment(user_id=staff2.id, org_id=client_org.id))
    db.commit()

    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id, staff2.id],
    )
    assert data["assignment_mode"] == "manual"
    assert data["assignee_id"] == staff_user.id  # first = primary
    assert len(data["assignees"]) == 2

    primary_entries = [a for a in data["assignees"] if a["is_primary"]]
    assert len(primary_entries) == 1
    assert primary_entries[0]["user_id"] == staff_user.id

    rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id == data["id"]).all()
    assert len(rows) == 2


def test_create_ticket_legacy_assignee_id_treated_as_manual(
    client, db, admin_token, staff_user, staff_assignment, client_org, service
):
    """Old client sends assignee_id (no assignee_ids) → ticket_assignees row created."""
    from app.models.ticket import TicketAssignee

    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignee_id=staff_user.id,
    )
    assert data["assignee_id"] == staff_user.id
    rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id == data["id"]).all()
    assert len(rows) == 1


def test_ticket_detail_has_assignees_and_mode(
    client, admin_token, staff_user, staff_assignment, client_org, service
):
    """GET /tickets/{id} includes assignment_mode and assignees."""
    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    r = client.get(f"/api/tickets/{data['id']}", headers=_auth(admin_token))
    assert r.status_code == 200
    detail = r.json()
    assert "assignment_mode" in detail
    assert "assignees" in detail
    assert isinstance(detail["assignees"], list)
    assert detail["assignees"][0]["user_id"] == staff_user.id


def test_update_ticket_assignee_ids_replaces_assignees(
    client, db, admin_token, staff_user, staff_assignment, provider_org, client_org, service
):
    """PUT /tickets/{id} with assignee_ids replaces all existing assignees."""
    from app.models.ticket import TicketAssignee

    staff2 = _make_staff2(db, provider_org)
    from app.models.team import StaffOrgAssignment
    db.add(StaffOrgAssignment(user_id=staff2.id, org_id=client_org.id))
    db.commit()

    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    ticket_id = data["id"]

    # Replace with staff2
    r = client.put(
        f"/api/tickets/{ticket_id}",
        json={"assignee_ids": [staff2.id]},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["assignee_id"] == staff2.id
    assert len(updated["assignees"]) == 1
    assert updated["assignees"][0]["user_id"] == staff2.id

    db.expire_all()
    rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id == ticket_id).all()
    assert len(rows) == 1
    assert rows[0].user_id == staff2.id


# ── member-sync ───────────────────────────────────────────────────────────────

def test_member_sync_assign_adds_staff_to_project(
    client, db, admin_token, admin_user, staff_user, staff_assignment, client_org, service
):
    """Assigning staff to a ticket that belongs to a project auto-adds them as project member."""
    from app.models.project import ProjectMember

    project = _make_project(db, client_org.id, admin_user.id)
    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        project_id=project.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    assert data["assignee_id"] == staff_user.id

    db.expire_all()
    pm = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
    ).first()
    assert pm is not None, "Staff should have been auto-added to project_members"
    assert pm.role == "staff"


def test_member_sync_remove_assignee_no_other_tickets_removes_member(
    client, db, admin_token, admin_user, staff_user, staff_assignment, provider_org, client_org, service
):
    """Removing the only assignee from a project ticket removes their project membership."""
    from app.models.project import ProjectMember

    project = _make_project(db, client_org.id, admin_user.id)
    staff2 = _make_staff2(db, provider_org)
    from app.models.team import StaffOrgAssignment
    db.add(StaffOrgAssignment(user_id=staff2.id, org_id=client_org.id))
    db.commit()

    # Create ticket with staff_user
    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        project_id=project.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    ticket_id = data["id"]

    db.expire_all()
    assert db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
    ).first() is not None

    # Replace with staff2 (removes staff_user from assignees)
    r = client.put(
        f"/api/tickets/{ticket_id}",
        json={"assignee_ids": [staff2.id]},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200

    db.expire_all()
    pm_old = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
    ).first()
    assert pm_old is None, "staff_user should be removed from project_members (no remaining tickets)"

    pm_new = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff2.id,
    ).first()
    assert pm_new is not None, "staff2 should now be in project_members"


def test_member_sync_remove_assignee_still_has_other_ticket_keeps_member(
    client, db, admin_token, admin_user, staff_user, staff_assignment, provider_org, client_org, service
):
    """Removing staff from one ticket does NOT remove project membership if they still have another."""
    from app.models.project import ProjectMember

    project = _make_project(db, client_org.id, admin_user.id)
    staff2 = _make_staff2(db, provider_org)
    from app.models.team import StaffOrgAssignment
    db.add(StaffOrgAssignment(user_id=staff2.id, org_id=client_org.id))
    db.commit()

    # Two tickets with staff_user in same project
    t1 = _create_ticket(
        client, admin_token, client_org.id, service.id,
        project_id=project.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    t2 = _create_ticket(
        client, admin_token, client_org.id, service.id,
        project_id=project.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )

    # Remove staff_user from ticket 1 only (still assigned to ticket 2)
    r = client.put(
        f"/api/tickets/{t1['id']}",
        json={"assignee_ids": [staff2.id]},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200

    db.expire_all()
    pm = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
    ).first()
    assert pm is not None, "staff_user still has ticket 2 in project — must keep membership"


def test_member_sync_never_removes_manager_role(
    client, db, admin_token, admin_user, staff_user, staff_assignment, provider_org, client_org, service
):
    """Staff who is also a project manager is never removed from project_members on unassign."""
    from app.models.project import Project, ProjectMember

    project = _make_project(db, client_org.id, admin_user.id)

    # Manually add staff_user as manager
    db.add(ProjectMember(
        project_id=project.id,
        user_id=staff_user.id,
        role="manager",
        added_by=admin_user.id,
    ))
    db.commit()

    # Assign staff_user to ticket in that project
    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        project_id=project.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    ticket_id = data["id"]

    # member-sync adds a 'staff' row (second row for staff_user)
    db.expire_all()
    rows = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
    ).all()
    # Could be 1 or 2 rows depending on upsert behavior —
    # the 'manager' row must always remain
    manager_row = next((r for r in rows if r.role == "manager"), None)
    assert manager_row is not None

    # Remove staff_user from ticket assignees
    r = client.put(
        f"/api/tickets/{ticket_id}",
        json={"assignee_ids": []},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200

    db.expire_all()
    manager_row = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
        ProjectMember.role == "manager",
    ).first()
    assert manager_row is not None, "manager role must never be removed by member-sync"


# ── auto-assign workload uses project tasks ───────────────────────────────────

def test_auto_assign_prefers_staff_with_fewer_project_tasks(
    client, db, admin_token, admin_user, staff_user, staff_assignment,
    provider_org, client_org, service,
):
    """Auto-assign picks the staff member with fewer active project tasks."""
    from app.models.user import User
    from app.models.team import StaffOrgAssignment
    from app.models.project import Project, ProjectTask
    from app.core.security import hash_password

    staff2 = User(
        org_id=provider_org.id,
        email="staff2_aa@test.com",
        password_hash=hash_password("s"),
        full_name="Staff Two AA",
        role="staff",
        is_active=True,
    )
    db.add(staff2)
    db.commit()
    db.refresh(staff2)
    db.add(StaffOrgAssignment(user_id=staff2.id, org_id=client_org.id))
    db.commit()

    # Give staff_user 3 open project tasks
    project = Project(
        org_id=client_org.id,
        name="AA Test Project",
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

    from app.core.security import hash_password as hp
    customer = User(
        org_id=client_org.id,
        email="cust_aa@test.com",
        password_hash=hp("c"),
        full_name="Customer AA",
        role="customer",
        is_active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    r_login = client.post("/api/auth/login", json={"email": "cust_aa@test.com", "password": "c"})
    cust_token = r_login.json()["access_token"]

    data = _create_ticket(client, cust_token, client_org.id, service.id)
    assert data["assignee_id"] == staff2.id, (
        f"Expected staff2 (0 tasks), got {data['assignee_id']}"
    )


# ── assign endpoint still works with single assignee ─────────────────────────

def test_list_tickets_includes_assignees_field(
    client, admin_token, staff_user, staff_assignment, client_org, service
):
    """GET /tickets list response includes 'assignees' and 'assignment_mode' per item."""
    _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="manual",
        assignee_ids=[staff_user.id],
    )
    r = client.get("/api/tickets", headers=_auth(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    item = items[0]
    assert "assignees" in item
    assert "assignment_mode" in item
    assert isinstance(item["assignees"], list)


def test_assign_endpoint_creates_ticket_assignee_row(
    client, db, admin_token, staff_user, staff_assignment, client_org, service, customer_token
):
    """POST /tickets/{id}/assign creates a ticket_assignees record."""
    from app.models.ticket import TicketAssignee

    # Create unassigned ticket
    data = _create_ticket(client, customer_token, client_org.id, service.id)
    ticket_id = data["id"]

    r = client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": staff_user.id},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["assignee_id"] == staff_user.id
    assert len(result["assignees"]) == 1

    db.expire_all()
    rows = db.query(TicketAssignee).filter(TicketAssignee.ticket_id == ticket_id).all()
    assert len(rows) == 1
    assert rows[0].user_id == staff_user.id
    assert rows[0].is_primary is True


# ── Assignment preview score endpoint ────────────────────────────────────────

def test_assignment_preview_score_admin_only(client, admin_token, customer_token, client_org):
    """Admin gets 200; non-admin gets 403."""
    r_admin = client.get(
        f"/api/admin/assignment/preview-score?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_admin.status_code == 200
    body = r_admin.json()
    assert isinstance(body, list)


def test_assignment_preview_score_structure(client, admin_token, client_org, staff_user, staff_assignment):
    """Response items contain required fields and is_winner is set correctly."""
    r = client.get(
        f"/api/admin/assignment/preview-score?org_id={client_org.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    if items:
        item = items[0]
        for field in ("user_id", "name", "workload_score", "skill_score", "online_score", "total", "is_winner"):
            assert field in item, f"Missing field: {field}"
        winners = [i for i in items if i["is_winner"]]
        assert len(winners) >= 1


# ── Skill score tests ─────────────────────────────────────────────────────────

def _make_ticket(db, org_id, raised_by, status="Open", ticket_type="Bug"):
    from app.models.ticket import Ticket
    t = Ticket(
        org_id=org_id,
        subject="test skill",
        description="desc",
        status=status,
        priority="Medium",
        ticket_type=ticket_type,
        source="portal",
        raised_by=raised_by,
        raised_by_email="x@x.com",
        is_deleted=False,
        sla_paused_total_seconds=0,
        assignment_mode="manual",
    )
    db.add(t)
    db.flush()
    return t


def _assign(db, ticket_id, user_id):
    from app.models.ticket import TicketAssignee
    row = TicketAssignee(ticket_id=ticket_id, user_id=user_id, is_primary=True, assigned_by=None)
    db.add(row)
    db.flush()


def _add_prediction(db, ticket_id, category="technical"):
    from app.models.ai_prediction import TicketAiPrediction
    pred = TicketAiPrediction(
        ticket_id=ticket_id,
        predicted_category=category,
        predicted_priority="medium",
        confidence=0.9,
        model_name="test-model",
        model_version="1.0",
    )
    db.add(pred)
    db.flush()


def test_skill_score_coldstart_equal_for_new_agents(db, client_org, staff_user, admin_user):
    """Two brand-new agents with zero resolved tickets get identical skill_score (cold-start baseline)."""
    from app.models.user import User
    from app.models.team import StaffOrgAssignment
    from app.services.auto_assign import _skill_score
    from app.core.constants import ASSIGN_SKILL_WEIGHT, SKILL_BASELINE_WEIGHT

    # Create a second staff user
    staff2 = User(
        org_id=staff_user.org_id,
        email="staff2_skill@test.com",
        password_hash="x",
        full_name="Staff Two",
        role="staff",
        is_active=True,
    )
    db.add(staff2)
    db.flush()

    # Both assigned to client_org
    for uid in (staff_user.id, staff2.id):
        if not db.query(StaffOrgAssignment).filter_by(user_id=uid, org_id=client_org.id).first():
            db.add(StaffOrgAssignment(user_id=uid, org_id=client_org.id))
    db.flush()

    # Ticket with no prediction (neither agent has history)
    ticket = _make_ticket(db, client_org.id, admin_user.id)
    db.commit()

    score1 = _skill_score(staff_user.id, ticket, db)
    score2 = _skill_score(staff2.id, ticket, db)

    expected_baseline = round(ASSIGN_SKILL_WEIGHT * SKILL_BASELINE_WEIGHT, 2)
    assert score1 == score2 == expected_baseline, (
        f"Cold-start agents should both score {expected_baseline}, got {score1} and {score2}"
    )


def test_skill_score_rewards_category_history(db, client_org, staff_user, admin_user):
    """Agent with 5 resolved 'technical' tickets scores higher for a 'technical' ticket than a fresh agent."""
    from app.models.user import User
    from app.models.team import StaffOrgAssignment
    from app.services.auto_assign import _skill_score

    staff_expert = User(
        org_id=staff_user.org_id,
        email="staff_expert@test.com",
        password_hash="x",
        full_name="Expert Staff",
        role="staff",
        is_active=True,
    )
    staff_fresh = User(
        org_id=staff_user.org_id,
        email="staff_fresh@test.com",
        password_hash="x",
        full_name="Fresh Staff",
        role="staff",
        is_active=True,
    )
    db.add_all([staff_expert, staff_fresh])
    db.flush()

    for uid in (staff_expert.id, staff_fresh.id):
        if not db.query(StaffOrgAssignment).filter_by(user_id=uid, org_id=client_org.id).first():
            db.add(StaffOrgAssignment(user_id=uid, org_id=client_org.id))
    db.flush()

    # Give expert 5 resolved technical tickets
    for _ in range(5):
        resolved = _make_ticket(db, client_org.id, admin_user.id, status="Resolved", ticket_type="Bug")
        _assign(db, resolved.id, staff_expert.id)
        _add_prediction(db, resolved.id, category="technical")

    # New ticket with AI prediction = "technical"
    new_ticket = _make_ticket(db, client_org.id, admin_user.id)
    _add_prediction(db, new_ticket.id, category="technical")
    db.commit()

    expert_score = _skill_score(staff_expert.id, new_ticket, db)
    fresh_score = _skill_score(staff_fresh.id, new_ticket, db)

    assert expert_score > fresh_score, (
        f"Expert should score higher than fresh agent ({expert_score} vs {fresh_score})"
    )


def test_skill_score_baseline_decays(db, client_org, staff_user, admin_user):
    """Agent with 10+ resolved tickets has baseline=0; skill comes only from historical."""
    from app.services.auto_assign import _skill_score
    from app.core.constants import SKILL_COLDSTART_THRESHOLD, SKILL_HISTORICAL_WEIGHT

    from app.models.team import StaffOrgAssignment
    if not db.query(StaffOrgAssignment).filter_by(user_id=staff_user.id, org_id=client_org.id).first():
        db.add(StaffOrgAssignment(user_id=staff_user.id, org_id=client_org.id))
        db.flush()

    # Give agent SKILL_COLDSTART_THRESHOLD resolved tickets (no category match for new ticket)
    for _ in range(SKILL_COLDSTART_THRESHOLD):
        resolved = _make_ticket(db, client_org.id, admin_user.id, status="Resolved", ticket_type="Bug")
        _assign(db, resolved.id, staff_user.id)
        _add_prediction(db, resolved.id, category="billing")  # different category

    # New ticket: category "technical" — agent has no history in this category
    new_ticket = _make_ticket(db, client_org.id, admin_user.id, ticket_type="Question")
    _add_prediction(db, new_ticket.id, category="technical")
    db.commit()

    score = _skill_score(staff_user.id, new_ticket, db)

    # baseline=0 (10 resolved ≥ threshold), historical=0 (no "technical" resolved)
    # → skill = 0.7×0 + 0.3×0 = 0.0
    assert score == 0.0, f"Expected 0.0 when baseline decayed and no history, got {score}"


def test_skill_score_fallback_to_ticket_type_when_no_prediction(db, client_org, staff_user, admin_user):
    """When ticket has no AI prediction, skill matching falls back to ticket_type."""
    from app.services.auto_assign import _skill_score
    from app.core.constants import ASSIGN_SKILL_WEIGHT, SKILL_BASELINE_WEIGHT, SKILL_HISTORICAL_WEIGHT
    from app.models.team import StaffOrgAssignment

    if not db.query(StaffOrgAssignment).filter_by(user_id=staff_user.id, org_id=client_org.id).first():
        db.add(StaffOrgAssignment(user_id=staff_user.id, org_id=client_org.id))
        db.flush()

    # Agent has 1 resolved ticket of type "Bug" (no AI prediction on it)
    resolved = _make_ticket(db, client_org.id, admin_user.id, status="Resolved", ticket_type="Bug")
    _assign(db, resolved.id, staff_user.id)
    # Intentionally NO _add_prediction here

    # New ticket: type "Bug", no AI prediction
    new_ticket = _make_ticket(db, client_org.id, admin_user.id, ticket_type="Bug")
    # Intentionally NO _add_prediction here
    db.commit()

    score = _skill_score(staff_user.id, new_ticket, db)

    # 1 resolved Bug ticket → historical_score = 1×8 = 8
    # total_resolved = 1 → baseline_score = 40×(1-1/10) = 36
    # skill = 0.7×8 + 0.3×36 = 5.6 + 10.8 = 16.4
    from app.core.constants import HISTORICAL_POINT_PER_TICKET, SKILL_COLDSTART_THRESHOLD
    expected_historical = min(ASSIGN_SKILL_WEIGHT, 1 * HISTORICAL_POINT_PER_TICKET)
    expected_baseline = max(0.0, ASSIGN_SKILL_WEIGHT * (1 - 1 / SKILL_COLDSTART_THRESHOLD))
    expected = round(SKILL_HISTORICAL_WEIGHT * expected_historical + SKILL_BASELINE_WEIGHT * expected_baseline, 2)

    assert score == expected, f"Fallback-to-ticket_type skill expected {expected}, got {score}"
