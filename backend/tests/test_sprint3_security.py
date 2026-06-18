"""Sprint 3 Security Tests — covers all C/H/M fixes introduced in Sprint 3."""
import hashlib
import pytest
from datetime import datetime, timedelta


# ─── helpers ──────────────────────────────────────────────────────────────────

def _org(db, name="Sprint3Org", code=None):
    from app.models.organization import Organization
    import uuid
    o = Organization(name=name, code=code or f"S3-{uuid.uuid4().hex[:6].upper()}", status="active")
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _user(db, org_id, email, role="customer", password="pass1234"):
    from app.models.user import User
    from app.core.security import hash_password
    u = User(org_id=org_id, email=email, full_name=email.split("@")[0],
             password_hash=hash_password(password), role=role, is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _token(client, email, password="pass1234"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _ticket(db, org_id, raised_by, service_id=None, assignee_id=None):
    from app.models.ticket import Ticket
    t = Ticket(org_id=org_id, subject="Sprint3 Ticket", status="Open",
               priority="Medium", ticket_type="incident",
               raised_by=raised_by, raised_by_email="x@x.com",
               service_id=service_id, assignee_id=assignee_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _assign_staff(db, user_id, org_id):
    from app.models.team import StaffOrgAssignment
    a = StaffOrgAssignment(user_id=user_id, org_id=org_id)
    db.add(a)
    db.commit()
    return a


# ══════════════════════════════════════════════════════════════════════════════
# C1 — Reset token reuse via JTI (password reset regression fix)
# ══════════════════════════════════════════════════════════════════════════════

def test_c1_full_reset_flow_succeeds(db, client):
    """Happy path: OTP → verify → reset password works end-to-end."""
    org = _org(db, "C1Org", "C1ORG")
    user = _user(db, org.id, "c1_reset@test.com", role="customer")

    otp_code = "111222"
    from app.models.password_reset import PasswordResetOTP
    otp_row = PasswordResetOTP(
        user_id=user.id,
        otp_hash=hashlib.sha256(otp_code.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(otp_row)
    db.commit()

    verify_res = client.post("/api/auth/verify-otp", json={"email": user.email, "otp": otp_code})
    assert verify_res.status_code == 200, verify_res.text
    reset_token = verify_res.json()["reset_token"]

    reset_res = client.post("/api/auth/reset-password", json={
        "reset_token": reset_token,
        "new_password": "newpassword99",
    })
    assert reset_res.status_code == 200, reset_res.text
    assert "Password updated" in reset_res.json()["message"]

    # Can now login with new password
    login_res = client.post("/api/auth/login", json={"email": user.email, "password": "newpassword99"})
    assert login_res.status_code == 200


def test_c1_reset_token_rejected_on_second_use(db, client):
    """Error path: using reset_token a second time → 400."""
    org = _org(db, "C1bOrg", "C1BORG")
    user = _user(db, org.id, "c1_reuse@test.com", role="customer")

    otp_code = "333444"
    from app.models.password_reset import PasswordResetOTP
    otp_row = PasswordResetOTP(
        user_id=user.id,
        otp_hash=hashlib.sha256(otp_code.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(otp_row)
    db.commit()

    verify_res = client.post("/api/auth/verify-otp", json={"email": user.email, "otp": otp_code})
    assert verify_res.status_code == 200
    reset_token = verify_res.json()["reset_token"]

    r1 = client.post("/api/auth/reset-password", json={"reset_token": reset_token, "new_password": "firstpass1"})
    assert r1.status_code == 200

    r2 = client.post("/api/auth/reset-password", json={"reset_token": reset_token, "new_password": "secondpass1"})
    assert r2.status_code == 400
    detail = r2.json()["detail"].lower()
    assert "already used" in detail or "expired" in detail


# ══════════════════════════════════════════════════════════════════════════════
# H2 — Ticket delete scoped to accessible orgs
# ══════════════════════════════════════════════════════════════════════════════

def test_h2_admin_can_soft_delete_any_ticket(db, client, admin_user, admin_token, client_org, customer_user):
    """Happy path: admin deletes ticket from any org."""
    ticket = _ticket(db, client_org.id, customer_user.id)
    r = client.delete(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200

    db.expire_all()
    from app.models.ticket import Ticket
    t = db.query(Ticket).filter(Ticket.id == ticket.id).first()
    assert t.is_deleted is True


def test_h2_staff_cannot_soft_delete_out_of_scope_ticket(db, client, provider_org, client_org, customer_user):
    """Error path: staff without org assignment gets 404 on delete."""
    staff = _user(db, provider_org.id, "h2staff@test.com", role="staff")
    # No StaffOrgAssignment to client_org
    tok = _token(client, "h2staff@test.com")
    ticket = _ticket(db, client_org.id, customer_user.id)
    r = client.delete(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code in (403, 404)


def test_h2_admin_hard_delete_out_of_scope_still_works(db, client, admin_user, admin_token, client_org, customer_user):
    """Happy path: admin can hard-delete any ticket regardless of org."""
    ticket = _ticket(db, client_org.id, customer_user.id)
    # Soft-delete first
    client.delete(f"/api/tickets/{ticket.id}", headers={"Authorization": f"Bearer {admin_token}"})
    # Hard delete
    r = client.delete(f"/api/tickets/{ticket.id}/permanent", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# H3 — exclude_unset lets nullable fields be cleared
# ══════════════════════════════════════════════════════════════════════════════

def test_h3_can_clear_assignee_with_null(db, client, admin_token, client_org, customer_user, staff_user, staff_assignment):
    """Happy path: sending assignee_id=null explicitly clears the assignee."""
    ticket = _ticket(db, client_org.id, customer_user.id, assignee_id=staff_user.id)
    r = client.put(
        f"/api/tickets/{ticket.id}",
        json={"assignee_id": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee_id"] is None


def test_h3_omitting_assignee_does_not_clear_it(db, client, admin_token, client_org, customer_user, staff_user, staff_assignment):
    """Happy path: not sending assignee_id at all leaves it unchanged."""
    ticket = _ticket(db, client_org.id, customer_user.id, assignee_id=staff_user.id)
    r = client.put(
        f"/api/tickets/{ticket.id}",
        json={"priority": "High"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee_id"] == staff_user.id


def test_h3_empty_assignee_ids_clears_assignees(db, client, admin_token, client_org, customer_user, staff_user, staff_assignment):
    """Happy path: sending assignee_ids=[] clears all assignees."""
    ticket = _ticket(db, client_org.id, customer_user.id, assignee_id=staff_user.id)
    r = client.put(
        f"/api/tickets/{ticket.id}",
        json={"assignee_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee_id"] is None


# ══════════════════════════════════════════════════════════════════════════════
# H1 — Staff org check when linking user to contact
# ══════════════════════════════════════════════════════════════════════════════

def test_h1_cannot_link_unassigned_staff_to_contact(db, client, admin_token, provider_org, client_org):
    """Error path: staff not assigned to client_org cannot be linked to its contact."""
    from app.models.contact import Contact
    staff = _user(db, provider_org.id, "h1_unassigned@test.com", role="staff")
    # No assignment to client_org

    contact = Contact(org_id=client_org.id, name="Test Contact", email="contact@c.com")
    db.add(contact)
    db.commit()
    db.refresh(contact)

    r = client.put(
        f"/api/organizations/{client_org.id}/contacts/{contact.id}/link-user",
        json={"user_id": staff.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 403


def test_h1_can_link_assigned_staff_to_contact(db, client, admin_token, provider_org, client_org, staff_user, staff_assignment):
    """Happy path: staff assigned to client_org can be linked."""
    from app.models.contact import Contact
    contact = Contact(org_id=client_org.id, name="Contact2", email="c2@c.com")
    db.add(contact)
    db.commit()
    db.refresh(contact)

    r = client.put(
        f"/api/organizations/{client_org.id}/contacts/{contact.id}/link-user",
        json={"user_id": staff_user.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user_id"] == staff_user.id


# ══════════════════════════════════════════════════════════════════════════════
# M5 — Contact unlink scoped to org
# ══════════════════════════════════════════════════════════════════════════════

def test_m5_unlink_only_within_org(db, client, admin_token, client_org, second_client_org, customer_user):
    """Happy path: linking in org A does not unlink from org B's contacts."""
    from app.models.contact import Contact
    # contact_a in client_org linked to customer_user
    contact_a = Contact(org_id=client_org.id, name="CA", email="ca@x.com", user_id=customer_user.id)
    # contact_b in second_client_org also linked to customer_user (cross-org scenario)
    contact_b = Contact(org_id=second_client_org.id, name="CB", email="cb@x.com", user_id=customer_user.id)
    db.add_all([contact_a, contact_b])
    db.commit()
    db.refresh(contact_a)
    db.refresh(contact_b)

    # Link customer_user to a NEW contact in client_org → should unlink from contact_a (same org)
    contact_new = Contact(org_id=client_org.id, name="CNew", email="cnew@x.com")
    db.add(contact_new)
    db.commit()
    db.refresh(contact_new)

    r = client.put(
        f"/api/organizations/{client_org.id}/contacts/{contact_new.id}/link-user",
        json={"user_id": customer_user.id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200

    db.expire_all()
    # contact_a in same org should be unlinked
    ca = db.query(Contact).filter(Contact.id == contact_a.id).first()
    assert ca.user_id is None
    # contact_b in different org must NOT be unlinked
    cb = db.query(Contact).filter(Contact.id == contact_b.id).first()
    assert cb.user_id == customer_user.id


# ══════════════════════════════════════════════════════════════════════════════
# M6 — Transfer request GET requires ticket scope
# ══════════════════════════════════════════════════════════════════════════════

def test_m6_get_transfer_request_out_of_scope_returns_404(db, client, provider_org, client_org, customer_user, second_client_org):
    """Error path: customer from different org cannot see transfer request."""
    other_cust = _user(db, second_client_org.id, "m6other@test.com", role="customer")
    ticket = _ticket(db, client_org.id, customer_user.id)
    tok = _token(client, "m6other@test.com")

    r = client.get(f"/api/tickets/{ticket.id}/transfer-request",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


def test_m6_get_transfer_request_in_scope_succeeds(db, client, client_org, customer_user, customer_token):
    """Happy path: ticket owner sees transfer request (None when no pending)."""
    ticket = _ticket(db, client_org.id, customer_user.id)
    r = client.get(f"/api/tickets/{ticket.id}/transfer-request",
                   headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 200
    assert r.json() is None  # no pending request


# ══════════════════════════════════════════════════════════════════════════════
# M7 — Transfer target must be org-assigned
# ══════════════════════════════════════════════════════════════════════════════

def test_m7_transfer_to_unassigned_staff_fails(db, client, provider_org, client_org, customer_user, staff_user, staff_assignment):
    """Error path: transfer to staff not assigned to ticket's org → 400."""
    unassigned_staff = _user(db, provider_org.id, "m7unassigned@test.com", role="staff")
    ticket = _ticket(db, client_org.id, customer_user.id, assignee_id=staff_user.id)
    tok = _token(client, "staff@test.com", "staff123")

    r = client.post(
        f"/api/tickets/{ticket.id}/transfer-request",
        json={"to_staff_id": unassigned_staff.id},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 400


def test_m7_transfer_to_assigned_staff_succeeds(db, client, provider_org, client_org, customer_user, staff_user, staff_assignment):
    """Happy path: transfer to staff assigned to ticket's org → 201."""
    target = _user(db, provider_org.id, "m7target@test.com", role="staff")
    _assign_staff(db, target.id, client_org.id)
    ticket = _ticket(db, client_org.id, customer_user.id, assignee_id=staff_user.id)
    tok = _token(client, "staff@test.com", "staff123")

    r = client.post(
        f"/api/tickets/{ticket.id}/transfer-request",
        json={"to_staff_id": target.id},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"


# ══════════════════════════════════════════════════════════════════════════════
# M3 — Customer must be project member to list members
# ══════════════════════════════════════════════════════════════════════════════

def _make_project(db, org_id, name="Sprint3 Project", created_by=None):
    from app.models.project import Project
    if created_by is None:
        # Need a valid user_id; fetch any existing user or create a placeholder
        from app.models.user import User
        u = db.query(User).filter(User.org_id == org_id).first()
        if u is None:
            raise ValueError(f"No user in org {org_id} to use as created_by")
        created_by = u.id
    p = Project(org_id=org_id, name=name, status="open", visibility="customer_visible",
                created_by=created_by)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_m3_customer_not_member_cannot_list_project_members(db, client, client_org, customer_user, customer_token):
    """Error path: customer in correct org but not a project member → 404."""
    project = _make_project(db, client_org.id, created_by=customer_user.id)
    r = client.get(f"/api/projects/{project.id}/members",
                   headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 404


def test_m3_customer_member_can_list_project_members(db, client, client_org, customer_user, customer_token, admin_user, admin_token):
    """Happy path: customer explicitly added as project member → 200."""
    project = _make_project(db, client_org.id, "M3 Project", created_by=customer_user.id)

    # Add customer as project member
    from app.models.project import ProjectMember
    member = ProjectMember(project_id=project.id, user_id=customer_user.id, role="customer", added_by=admin_user.id)
    db.add(member)
    db.commit()

    r = client.get(f"/api/projects/{project.id}/members",
                   headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert any(m["user_id"] == customer_user.id for m in data)


# ══════════════════════════════════════════════════════════════════════════════
# M4 — Non-visible task returns 404 not 403
# ══════════════════════════════════════════════════════════════════════════════

def _make_task(db, project_id, title="Sprint3 Task", is_client_visible=True):
    from app.models.project import ProjectTask
    t = ProjectTask(project_id=project_id, title=title, status="open",
                    is_client_visible=is_client_visible)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_m4_invisible_task_returns_404_not_403_for_approval(db, client, client_org, customer_user, customer_token, admin_user):
    """Error path: customer requests approval on non-client-visible task → 404 (not 403)."""
    project = _make_project(db, client_org.id, "M4 Project", created_by=customer_user.id)
    from app.models.project import ProjectMember
    member = ProjectMember(project_id=project.id, user_id=customer_user.id, role="customer", added_by=admin_user.id)
    db.add(member)
    db.commit()
    task = _make_task(db, project.id, is_client_visible=False)

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "submitted_for_review"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 404


def test_m4_invisible_task_returns_404_for_list_approvals(db, client, client_org, customer_user, customer_token, admin_user):
    """Error path: customer lists approvals on non-visible task → 404."""
    project = _make_project(db, client_org.id, "M4b Project", created_by=customer_user.id)
    from app.models.project import ProjectMember
    member = ProjectMember(project_id=project.id, user_id=customer_user.id, role="customer", added_by=admin_user.id)
    db.add(member)
    db.commit()
    task = _make_task(db, project.id, is_client_visible=False)

    r = client.get(
        f"/api/project-tasks/{task.id}/approvals",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# M12 — Customer cannot see inactive items
# ══════════════════════════════════════════════════════════════════════════════

def _make_item(db, name, is_active=True):
    from app.models.item import Item
    item = Item(code=f"ITM-{name.upper()[:6]}", name=name, type="support",
                unit_price=10.0, is_active=is_active)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_m12_customer_cannot_see_inactive_items_in_list(db, client, customer_token):
    """Error path: customer with is_active=false query param → still only gets active items."""
    active_item = _make_item(db, "ActiveItem")
    inactive_item = _make_item(db, "InactiveItem", is_active=False)

    r = client.get(
        "/api/items?paginated=true&is_active=false",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r.status_code == 200, r.text
    ids = [i["id"] for i in r.json()["items"]]
    assert inactive_item.id not in ids
    assert active_item.id in ids


def test_m12_customer_cannot_get_inactive_item_by_id(db, client, customer_token):
    """Error path: customer fetches an inactive item directly → 404."""
    inactive = _make_item(db, "InactiveGetTest", is_active=False)
    r = client.get(f"/api/items/{inactive.id}", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 404


def test_m12_admin_can_see_inactive_items(db, client, admin_token):
    """Happy path: admin can fetch inactive items."""
    inactive = _make_item(db, "AdminInactive", is_active=False)
    r = client.get(f"/api/items/{inactive.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_m12_customer_list_active_only_without_param(db, client, customer_token):
    """Happy path: customer sees only active items even with paginated=false."""
    active = _make_item(db, "VisibleActive")
    inactive = _make_item(db, "HiddenInactive", is_active=False)
    r = client.get("/api/items", headers={"Authorization": f"Bearer {customer_token}"})
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()] if isinstance(r.json(), list) else [i["id"] for i in r.json().get("items", [])]
    assert active.id in ids
    assert inactive.id not in ids


# ══════════════════════════════════════════════════════════════════════════════
# M2 — Task status update uses assert_project_task_access
# ══════════════════════════════════════════════════════════════════════════════

def test_m2_staff_cannot_update_task_outside_assigned_org(db, client, provider_org, client_org, customer_user):
    """Error path: staff without org assignment cannot update task status."""
    staff = _user(db, provider_org.id, "m2staff@test.com", role="staff")
    # No assignment to client_org
    tok = _token(client, "m2staff@test.com")
    project = _make_project(db, client_org.id, "M2 Project", created_by=customer_user.id)
    task = _make_task(db, project.id)

    r = client.patch(
        f"/api/project-tasks/{task.id}/status",
        json={"status": "working"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 404


def test_m2_staff_can_update_task_in_assigned_org(db, client, provider_org, client_org, customer_user, staff_user, staff_assignment):
    """Happy path: staff assigned to org can update task status."""
    tok = _token(client, "staff@test.com", "staff123")
    project = _make_project(db, client_org.id, "M2b Project", created_by=customer_user.id)
    task = _make_task(db, project.id)

    r = client.patch(
        f"/api/project-tasks/{task.id}/status",
        json={"status": "working"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "working"
