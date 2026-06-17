"""Tests for GET/POST/DELETE /api/projects/{id}/members endpoints."""
import pytest
from app.models.project import Project, ProjectMember


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_project(db, org_id, created_by, name="Test Project"):
    p = Project(
        org_id=org_id,
        name=name,
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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── list members ──────────────────────────────────────────────────────────────

def test_list_members_empty(client, db, admin_token, admin_user, client_org):
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.get(f"/api/projects/{project.id}/members", headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json() == []


def test_list_members_customer_can_see_own_org(
    client, db, customer_token, customer_user, client_org, admin_user, admin_token
):
    project = _make_project(db, client_org.id, admin_user.id)
    # Admin adds customer as member
    client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "customer"},
        headers=_auth(admin_token),
    )
    r = client.get(f"/api/projects/{project.id}/members", headers=_auth(customer_token))
    assert r.status_code == 200
    members = r.json()
    assert len(members) == 1
    assert members[0]["user_id"] == customer_user.id
    assert members[0]["role"] == "customer"
    assert members[0]["user_full_name"] == customer_user.full_name
    assert members[0]["user_email"] == customer_user.email


# ── add member ────────────────────────────────────────────────────────────────

def test_admin_can_add_member(client, db, admin_token, admin_user, client_org, customer_user):
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "customer"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["user_id"] == customer_user.id
    assert data["role"] == "customer"
    assert data["added_by"] == admin_user.id


def test_staff_can_add_member_to_assigned_org(
    client, db, staff_token, staff_user, admin_user, client_org, customer_user, provider_org
):
    from app.models.team import StaffOrgAssignment
    # Assign staff to client_org
    assignment = StaffOrgAssignment(user_id=staff_user.id, org_id=client_org.id)
    db.add(assignment)
    db.commit()

    project = _make_project(db, client_org.id, admin_user.id)
    r = client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "customer"},
        headers=_auth(staff_token),
    )
    assert r.status_code == 201, r.text


def test_staff_cannot_add_member_to_unassigned_org(
    client, db, staff_token, staff_user, admin_user, client_org, customer_user
):
    # staff_user is NOT assigned to client_org — project is invisible → 404
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "customer"},
        headers=_auth(staff_token),
    )
    assert r.status_code in (403, 404), r.text


def test_customer_cannot_add_member(
    client, db, customer_token, customer_user, admin_user, client_org
):
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "customer"},
        headers=_auth(customer_token),
    )
    assert r.status_code == 403, r.text


def test_add_duplicate_member_returns_409(
    client, db, admin_token, admin_user, client_org, customer_user
):
    project = _make_project(db, client_org.id, admin_user.id)
    payload = {"user_id": customer_user.id, "role": "customer"}
    r1 = client.post(f"/api/projects/{project.id}/members", json=payload, headers=_auth(admin_token))
    assert r1.status_code == 201
    r2 = client.post(f"/api/projects/{project.id}/members", json=payload, headers=_auth(admin_token))
    assert r2.status_code == 409, r2.text


def test_add_member_invalid_role_returns_422(
    client, db, admin_token, admin_user, client_org, customer_user
):
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "superuser"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 422, r.text


def test_add_nonexistent_user_returns_404(
    client, db, admin_token, admin_user, client_org
):
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": 999999, "role": "staff"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 404, r.text


def test_add_customer_from_wrong_org_returns_422(
    client, db, admin_token, admin_user, client_org, second_client_org, second_customer_user
):
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": second_customer_user.id, "role": "customer"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 422, r.text


# ── remove member ─────────────────────────────────────────────────────────────

def test_admin_can_remove_member(
    client, db, admin_token, admin_user, client_org, customer_user
):
    project = _make_project(db, client_org.id, admin_user.id)
    client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "customer"},
        headers=_auth(admin_token),
    )
    r = client.delete(
        f"/api/projects/{project.id}/members/{customer_user.id}",
        headers=_auth(admin_token),
    )
    assert r.status_code == 204

    # Verify removed
    r2 = client.get(f"/api/projects/{project.id}/members", headers=_auth(admin_token))
    assert r2.json() == []


def test_remove_nonexistent_member_returns_404(
    client, db, admin_token, admin_user, client_org
):
    project = _make_project(db, client_org.id, admin_user.id)
    r = client.delete(
        f"/api/projects/{project.id}/members/999999",
        headers=_auth(admin_token),
    )
    assert r.status_code == 404, r.text


# ── cascade delete ────────────────────────────────────────────────────────────

def test_project_delete_cascades_members(
    client, db, admin_token, admin_user, client_org, customer_user
):
    project = _make_project(db, client_org.id, admin_user.id)
    client.post(
        f"/api/projects/{project.id}/members",
        json={"user_id": customer_user.id, "role": "customer"},
        headers=_auth(admin_token),
    )
    # Verify member exists
    assert db.query(ProjectMember).filter(ProjectMember.project_id == project.id).count() == 1

    # Hard-delete project directly in DB to trigger CASCADE
    db.delete(project)
    db.commit()

    # Member row must be gone
    assert db.query(ProjectMember).filter(ProjectMember.project_id == project.id).count() == 0
