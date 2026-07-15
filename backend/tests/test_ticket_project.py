"""Tests for Sprint C: ticket ↔ project linking endpoints."""
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_project(db, org_id, created_by, name="Sprint C Project"):
    from app.models.project import Project
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


def _create_ticket(client, token, org_id, service_id, **extra):
    payload = {"org_id": org_id, "service_id": service_id, "subject": "Project test", **extra}
    r = client.post("/api/tickets", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _make_staff_user(db, provider_org, email="staff2_proj@test.com"):
    from app.models.user import User
    from app.core.security import hash_password
    u = User(
        org_id=provider_org.id,
        email=email,
        password_hash=hash_password("s"),
        full_name="Staff Proj",
        role="staff",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ── C.3 create-project ────────────────────────────────────────────────────────

def test_admin_creates_project_from_ticket(
    client, db, admin_token, admin_user, customer_user, client_org, service, staff_user, staff_assignment
):
    """Admin POST create-project: project created, ticket linked, attachments copied, members synced."""
    # Create a ticket with a manual assignee so member sync has something to do
    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="manual", assignee_ids=[staff_user.id],
    )
    ticket_id = data["id"]

    # Add a ticket attachment directly in DB
    from app.models.attachment import TicketAttachment
    att = TicketAttachment(
        ticket_id=ticket_id,
        reply_id=None,
        file_name="test.pdf",
        file_path="/uploads/test.pdf",
        file_size=1024,
        mime_type="application/pdf",
        uploaded_by=admin_user.id,
    )
    db.add(att)
    db.commit()

    r = client.post(f"/api/tickets/{ticket_id}/create-project", headers=_auth(admin_token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert "id" in body
    assert body["org_id"] == client_org.id

    # ticket.project_id should now be set
    r2 = client.get(f"/api/tickets/{ticket_id}", headers=_auth(admin_token))
    assert r2.status_code == 200
    ticket_detail = r2.json()
    assert ticket_detail["project_id"] == body["id"]

    # Attachment should be copied as a project document reference
    from app.models.project import ProjectDocument
    docs = db.query(ProjectDocument).filter(ProjectDocument.project_id == body["id"]).all()
    assert len(docs) == 1
    assert docs[0].source == "ticket_attachment"
    assert docs[0].ticket_attachment_id == att.id
    assert docs[0].file_name == "test.pdf"

    # Members synced: staff_user as staff, customer_user not assigned (raised_by is admin)
    from app.models.project import ProjectMember
    pm_staff = db.query(ProjectMember).filter(
        ProjectMember.project_id == body["id"],
        ProjectMember.user_id == staff_user.id,
    ).first()
    assert pm_staff is not None
    assert pm_staff.role == "staff"


def test_create_project_409_if_already_linked(
    client, db, admin_token, admin_user, client_org, service
):
    """create-project returns 409 when ticket is already linked to a project."""
    data = _create_ticket(client, admin_token, client_org.id, service.id, assignment_mode="none")
    ticket_id = data["id"]

    r1 = client.post(f"/api/tickets/{ticket_id}/create-project", headers=_auth(admin_token))
    assert r1.status_code == 201

    r2 = client.post(f"/api/tickets/{ticket_id}/create-project", headers=_auth(admin_token))
    assert r2.status_code == 409


def test_staff_cannot_create_project_from_ticket(
    client, db, staff_token, admin_user, client_org, service, staff_assignment
):
    """staff role gets 403 from create-project (admin-only endpoint)."""
    # Create ticket as admin, then try to create-project as staff
    r_login = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    admin_tok = r_login.json()["access_token"]
    data = _create_ticket(client, admin_tok, client_org.id, service.id, assignment_mode="none")
    ticket_id = data["id"]

    r = client.post(f"/api/tickets/{ticket_id}/create-project", headers=_auth(staff_token))
    assert r.status_code == 403


# ── C.3 link-project ─────────────────────────────────────────────────────────

def test_link_project_sets_project_id_and_logs_activity(
    client, db, admin_token, admin_user, client_org, service
):
    """POST link-project sets ticket.project_id and creates a TicketActivity."""
    data = _create_ticket(client, admin_token, client_org.id, service.id, assignment_mode="none")
    ticket_id = data["id"]

    project = _make_project(db, client_org.id, admin_user.id)

    r = client.post(
        f"/api/tickets/{ticket_id}/link-project",
        json={"project_id": project.id},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticket_id"] == ticket_id
    assert body["project_id"] == project.id
    assert body["project_name"] == project.name

    # Confirm ticket detail reflects the link
    r2 = client.get(f"/api/tickets/{ticket_id}", headers=_auth(admin_token))
    assert r2.json()["project_id"] == project.id
    assert r2.json()["project_name"] == project.name

    # Activity logged
    from app.models.ticket import TicketActivity
    act = db.query(TicketActivity).filter(
        TicketActivity.ticket_id == ticket_id,
        TicketActivity.action == "project_linked",
    ).first()
    assert act is not None
    assert act.to_value == str(project.id)


def test_link_project_wrong_org_returns_404(
    client, db, admin_token, admin_user, client_org, service, second_client_org
):
    """Linking a project that belongs to a different org returns 404."""
    data = _create_ticket(client, admin_token, client_org.id, service.id, assignment_mode="none")
    ticket_id = data["id"]

    other_project = _make_project(db, second_client_org.id, admin_user.id, name="Other Org Project")

    r = client.post(
        f"/api/tickets/{ticket_id}/link-project",
        json={"project_id": other_project.id},
        headers=_auth(admin_token),
    )
    assert r.status_code == 404


def test_link_project_already_linked_returns_409(
    client, db, admin_token, admin_user, client_org, service
):
    """Linking a different project when one is already linked returns 409."""
    data = _create_ticket(client, admin_token, client_org.id, service.id, assignment_mode="none")
    ticket_id = data["id"]

    p1 = _make_project(db, client_org.id, admin_user.id, name="Project One")
    p2 = _make_project(db, client_org.id, admin_user.id, name="Project Two")

    r1 = client.post(f"/api/tickets/{ticket_id}/link-project", json={"project_id": p1.id}, headers=_auth(admin_token))
    assert r1.status_code == 200

    r2 = client.post(f"/api/tickets/{ticket_id}/link-project", json={"project_id": p2.id}, headers=_auth(admin_token))
    assert r2.status_code == 409


# ── C.3 unlink-project ───────────────────────────────────────────────────────

def test_unlink_project_clears_project_id_keeps_members(
    client, db, admin_token, admin_user, client_org, service, staff_user, staff_assignment
):
    """DELETE unlink-project: project_id cleared, project members remain."""
    data = _create_ticket(
        client, admin_token, client_org.id, service.id,
        assignment_mode="manual", assignee_ids=[staff_user.id],
    )
    ticket_id = data["id"]

    project = _make_project(db, client_org.id, admin_user.id)

    # Link + let member sync fire
    r_link = client.post(
        f"/api/tickets/{ticket_id}/link-project",
        json={"project_id": project.id},
        headers=_auth(admin_token),
    )
    assert r_link.status_code == 200

    # Member should exist for staff_user
    from app.models.project import ProjectMember
    pm = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
    ).first()
    assert pm is not None

    # Unlink
    r_unlink = client.delete(f"/api/tickets/{ticket_id}/unlink-project", headers=_auth(admin_token))
    assert r_unlink.status_code == 200

    # project_id cleared
    r3 = client.get(f"/api/tickets/{ticket_id}", headers=_auth(admin_token))
    assert r3.json()["project_id"] is None

    # Members kept (spec: unlink keeps project_members)
    db.expire_all()
    pm_after = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == staff_user.id,
    ).first()
    assert pm_after is not None


# ── C.3 documents with source ─────────────────────────────────────────────────

def test_document_list_includes_source_and_ticket_attachment_id(
    client, db, admin_token, admin_user, client_org, service
):
    """GET /projects/{id}/documents returns source and ticket_attachment_id fields."""
    data = _create_ticket(client, admin_token, client_org.id, service.id, assignment_mode="none")
    ticket_id = data["id"]

    # Add ticket attachment
    from app.models.attachment import TicketAttachment
    att = TicketAttachment(
        ticket_id=ticket_id,
        reply_id=None,
        file_name="spec.docx",
        file_path="/uploads/spec.docx",
        file_size=2048,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        uploaded_by=admin_user.id,
    )
    db.add(att)
    db.commit()

    # Create project from ticket (copies attachments)
    r = client.post(f"/api/tickets/{ticket_id}/create-project", headers=_auth(admin_token))
    assert r.status_code == 201
    project_id = r.json()["id"]

    # Fetch project documents
    r_docs = client.get(f"/api/projects/{project_id}/documents", headers=_auth(admin_token))
    assert r_docs.status_code == 200
    docs = r_docs.json()
    assert len(docs) == 1
    doc = docs[0]
    assert doc["source"] == "ticket_attachment"
    assert doc["ticket_attachment_id"] == att.id
    assert doc["ticket_id"] == ticket_id


def test_link_project_rejects_cancelled_project(client, db, admin_token, client_org, service, admin_user):
    data = _create_ticket(client, admin_token, client_org.id, service.id, assignment_mode="none")
    ticket_id = data["id"]
    from app.models.project import Project
    project = Project(org_id=client_org.id, name="Cancelled Link", project_type="seo", status="cancelled", visibility="customer_visible", created_by=admin_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    r = client.post(
        f"/api/tickets/{ticket_id}/link-project",
        json={"project_id": project.id},
        headers=_auth(admin_token),
    )
    assert r.status_code == 422, r.text
