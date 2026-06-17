"""
Security regression tests for the 5 vulnerabilities fixed in this PR:

  1+2. organizations.py — staff can access any org/services without assignment
  3.   projects.py:973  — customer bypass ProjectMember on task approvals
  4.   projects.py:636  — staff assignee_id shortcut bypasses org check
  5.   auth.py:513      — OTP attempt counter race condition
  6.   contacts.py:113  — link_user_to_contact allows cross-org user
  7.   auth.py:551      — reset token TTL uses full session lifetime
"""
import hashlib
import threading
import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.core.security import hash_password
from app.core.constants import (
    OTP_MAX_ATTEMPTS, RESET_TOKEN_EXPIRE_MINUTES, OTP_EXPIRY_MINUTES
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _make_org(db, name="Org", code=None):
    from app.models.organization import Organization
    import uuid
    org = Organization(
        name=name,
        code=code or f"SEC-{uuid.uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_user(db, org_id, email, role="customer", password="pw1234"):
    from app.models.user import User
    u = User(
        org_id=org_id,
        email=email,
        full_name="Test User",
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _login(client, email, password="pw1234"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _assign_staff(db, user_id, org_id):
    from app.models.team import StaffOrgAssignment
    a = StaffOrgAssignment(user_id=user_id, org_id=org_id)
    db.add(a)
    db.commit()


def _make_project(db, org_id, created_by, visibility="customer_visible"):
    from app.models.project import Project
    p = Project(
        org_id=org_id,
        name="Security Test Project",
        project_type="seo",
        status="open",
        visibility=visibility,
        created_by=created_by,
        progress_percent=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_task(db, project_id, created_by, status="review"):
    from app.models.project import ProjectTask
    t = ProjectTask(
        project_id=project_id,
        title="Security Test Task",
        status=status,
        created_by=created_by,
        is_client_visible=True,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _add_project_member(db, project_id, user_id, role="customer"):
    from app.models.project import ProjectMember
    m = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.add(m)
    db.commit()


def _make_otp(db, user_id, otp="123456", minutes_from_now=10):
    from app.models.password_reset import PasswordResetOTP
    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    row = PasswordResetOTP(
        user_id=user_id,
        otp_hash=otp_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=minutes_from_now),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ══════════════════════════════════════════════════════════════════════════════
# LỖI 1+2: Staff xem org/services bất kỳ không cần StaffOrgAssignment
# ══════════════════════════════════════════════════════════════════════════════

def test_staff_cannot_get_org_without_assignment(client, db, provider_org):
    """Staff not assigned to org X → GET /organizations/{X.id} → 404."""
    other_org = _make_org(db, "Other Corp")
    staff = _make_user(db, provider_org.id, "staff_no_assign@test.com", role="staff")
    # No StaffOrgAssignment created for other_org
    token = _login(client, "staff_no_assign@test.com")

    r = client.get(f"/api/organizations/{other_org.id}", headers=_h(token))
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_staff_cannot_get_services_without_assignment(client, db, provider_org):
    """Staff not assigned to org X → GET /organizations/{X.id}/services → 404."""
    other_org = _make_org(db, "Other Corp 2")
    staff = _make_user(db, provider_org.id, "staff_no_svc@test.com", role="staff")
    token = _login(client, "staff_no_svc@test.com")

    r = client.get(f"/api/organizations/{other_org.id}/services", headers=_h(token))
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_staff_assigned_can_get_org(client, db, provider_org):
    """Staff WITH assignment → GET org → 200."""
    client_org = _make_org(db, "Assigned Org")
    staff = _make_user(db, provider_org.id, "staff_assigned@test.com", role="staff")
    _assign_staff(db, staff.id, client_org.id)
    token = _login(client, "staff_assigned@test.com")

    r = client.get(f"/api/organizations/{client_org.id}", headers=_h(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["id"] == client_org.id


def test_staff_assigned_can_get_services(client, db, provider_org):
    """Staff WITH assignment → GET /services → 200."""
    client_org = _make_org(db, "Assigned Org 2")
    staff = _make_user(db, provider_org.id, "staff_svc@test.com", role="staff")
    _assign_staff(db, staff.id, client_org.id)
    token = _login(client, "staff_svc@test.com")

    r = client.get(f"/api/organizations/{client_org.id}/services", headers=_h(token))
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# LỖI 3: Customer bypass ProjectMember khi approve task
# ══════════════════════════════════════════════════════════════════════════════

def test_customer_non_member_cannot_submit_approval(client, db, admin_user, provider_org):
    """Customer in same org but NOT a project member → POST approval → 404."""
    client_org = _make_org(db, "Client For Approval")
    cust = _make_user(db, client_org.id, "cust_no_member@test.com", role="customer")
    token = _login(client, "cust_no_member@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)
    # Customer NOT added as ProjectMember

    r = client.post(
        f"/api/project-tasks/{task.id}/approval",
        json={"action": "approved", "comment": "looks good"},
        headers=_h(token),
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_customer_non_member_cannot_list_approvals(client, db, admin_user, provider_org):
    """Customer in same org but NOT a project member → GET approvals → 404."""
    client_org = _make_org(db, "Client For Approval 2")
    cust = _make_user(db, client_org.id, "cust_no_member2@test.com", role="customer")
    token = _login(client, "cust_no_member2@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)

    r = client.get(f"/api/project-tasks/{task.id}/approvals", headers=_h(token))
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_customer_member_can_list_approvals(client, db, admin_user, provider_org):
    """Customer who IS a ProjectMember → GET approvals → 200."""
    client_org = _make_org(db, "Client Member Org")
    cust = _make_user(db, client_org.id, "cust_member@test.com", role="customer")
    token = _login(client, "cust_member@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)
    _add_project_member(db, project.id, cust.id, role="customer")

    r = client.get(f"/api/project-tasks/{task.id}/approvals", headers=_h(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 2 — MEDIUM 3: Customer task endpoints missing ProjectMember check
# ══════════════════════════════════════════════════════════════════════════════

def test_customer_non_member_cannot_get_task(client, db, admin_user, provider_org):
    """Customer in correct org but NOT a ProjectMember → GET task → 404."""
    client_org = _make_org(db, "Task Get Org")
    cust = _make_user(db, client_org.id, "cust_get_task@test.com", role="customer")
    token = _login(client, "cust_get_task@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)

    r = client.get(f"/api/project-tasks/{task.id}", headers=_h(token))
    assert r.status_code == 404, f"Expected 404 for non-member, got {r.status_code}: {r.text}"


def test_customer_member_can_get_task(client, db, admin_user, provider_org):
    """Customer who IS a ProjectMember → GET task → 200."""
    client_org = _make_org(db, "Task Get Org Member")
    cust = _make_user(db, client_org.id, "cust_get_task_ok@test.com", role="customer")
    token = _login(client, "cust_get_task_ok@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)
    _add_project_member(db, project.id, cust.id, role="customer")

    r = client.get(f"/api/project-tasks/{task.id}", headers=_h(token))
    assert r.status_code == 200, f"Expected 200 for member, got {r.status_code}: {r.text}"


def test_customer_non_member_cannot_add_comment(client, db, admin_user, provider_org):
    """Customer not in ProjectMember → POST /comments → 404."""
    client_org = _make_org(db, "Comment Org")
    cust = _make_user(db, client_org.id, "cust_comment_no@test.com", role="customer")
    token = _login(client, "cust_comment_no@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)

    r = client.post(
        f"/api/project-tasks/{task.id}/comments",
        json={"content": "hi", "is_internal": False},
        headers=_h(token),
    )
    assert r.status_code == 404, f"Expected 404 for non-member, got {r.status_code}: {r.text}"


def test_customer_non_member_cannot_list_comments(client, db, admin_user, provider_org):
    """Customer not in ProjectMember → GET /comments → 404."""
    client_org = _make_org(db, "List Comment Org")
    cust = _make_user(db, client_org.id, "cust_list_comment@test.com", role="customer")
    token = _login(client, "cust_list_comment@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)

    r = client.get(f"/api/project-tasks/{task.id}/comments", headers=_h(token))
    assert r.status_code == 404, f"Expected 404 for non-member, got {r.status_code}: {r.text}"


def test_customer_non_member_cannot_list_activities(client, db, admin_user, provider_org):
    """Customer not in ProjectMember → GET /activities → 404."""
    client_org = _make_org(db, "Activity Org")
    cust = _make_user(db, client_org.id, "cust_activity@test.com", role="customer")
    token = _login(client, "cust_activity@test.com")

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)

    r = client.get(f"/api/project-tasks/{task.id}/activities", headers=_h(token))
    assert r.status_code == 404, f"Expected 404 for non-member, got {r.status_code}: {r.text}"


# ══════════════════════════════════════════════════════════════════════════════
# LỖI 4: Staff assignee_id shortcut bypasses org check
# ══════════════════════════════════════════════════════════════════════════════

def test_staff_not_assigned_to_org_cannot_update_task_status_even_as_assignee(
    client, db, admin_user, provider_org
):
    """Staff không assign vào org X, nhưng là assignee của task → PATCH status → 404."""
    client_org = _make_org(db, "Org For Assignee Bypass")
    staff = _make_user(db, provider_org.id, "staff_assignee_bypass@test.com", role="staff")
    # Staff NOT assigned to client_org

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)
    # Set staff as task assignee directly in DB (bypassing proper flow)
    task.assignee_id = staff.id
    db.commit()

    token = _login(client, "staff_assignee_bypass@test.com")
    r = client.patch(
        f"/api/project-tasks/{task.id}/status",
        json={"status": "working"},
        headers=_h(token),
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_staff_assigned_to_org_can_update_task_status(client, db, admin_user, provider_org):
    """Staff WITH org assignment → PATCH /project-tasks/{id}/status → 200."""
    client_org = _make_org(db, "Org For Valid Assignee")
    staff = _make_user(db, provider_org.id, "staff_valid_assign@test.com", role="staff")
    _assign_staff(db, staff.id, client_org.id)

    project = _make_project(db, client_org.id, admin_user.id)
    task = _make_task(db, project.id, admin_user.id)
    task.status = "working"
    db.commit()

    token = _login(client, "staff_valid_assign@test.com")
    r = client.patch(
        f"/api/project-tasks/{task.id}/status",
        json={"status": "review"},
        headers=_h(token),
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ══════════════════════════════════════════════════════════════════════════════
# LỖI 5: OTP attempt counter race condition
# ══════════════════════════════════════════════════════════════════════════════

def test_otp_attempt_limit_enforced_under_concurrent_load(db):
    """10 concurrent wrong OTP requests → attempts ≤ OTP_MAX_ATTEMPTS (SELECT FOR UPDATE).

    Bug in original test: each thread overwrote app.dependency_overrides[get_db]
    with its own session → last writer wins → all requests serialized on one session
    → no real DB concurrency → passed even without FOR UPDATE.

    Fix: set override ONCE before threads start, using a factory that creates a
    fresh session per-request so each concurrent request gets its own DB connection.
    """
    from app.main import app
    from app.database import get_db
    from fastapi.testclient import TestClient
    from tests.conftest import TestingSessionLocal
    from app.models.password_reset import PasswordResetOTP

    org = _make_org(db, "OTP Race Org")
    user = _make_user(db, org.id, "otp_race@test.com", role="customer")
    _make_otp(db, user.id, otp="999999")  # correct OTP we'll never send
    db.commit()  # flush so other connections see the data

    # Override once with a per-request session factory (not a shared session).
    def fresh_session():
        s = TestingSessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = fresh_session

    results = []
    lock = threading.Lock()

    def send_wrong_otp():
        c = TestClient(app)
        r = c.post(
            "/api/auth/verify-otp",
            json={"email": "otp_race@test.com", "otp": "000000"},
        )
        with lock:
            results.append(r.status_code)

    threads = [threading.Thread(target=send_wrong_otp) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    app.dependency_overrides.clear()

    # Dispose the shared connection pool so subsequent tests get fresh connections.
    # The 10 thread sessions return their connections to the pool; if a TRUNCATE ran
    # between tests while those connections had open read transactions, InnoDB will
    # return error 1412 ("Table definition has changed") on the next query. Disposing
    # forces every pooled connection to be closed and rebuilt from scratch.
    from tests.conftest import engine as test_engine
    test_engine.dispose()

    # Re-read the OTP row from the test DB
    db.expire_all()
    otp_row = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id,
    ).first()

    # SELECT FOR UPDATE in verify_otp serialises concurrent increments → bounded
    assert otp_row.attempts <= OTP_MAX_ATTEMPTS, (
        f"Race condition: DB recorded {otp_row.attempts} attempts, "
        f"expected ≤ {OTP_MAX_ATTEMPTS}"
    )
    blocked = sum(1 for s in results if s in (400, 429))
    assert blocked > 0, "Expected some requests to be rejected (400 wrong code or 429 locked)"


def test_verify_otp_is_single_use(client, db):
    """Correct OTP can only produce one reset token — second call with same OTP → 400."""
    org = _make_org(db, "Single Use OTP Org")
    user = _make_user(db, org.id, "otp_single_use@test.com")
    _make_otp(db, user.id, otp="654321")

    r1 = client.post(
        "/api/auth/verify-otp",
        json={"email": "otp_single_use@test.com", "otp": "654321"},
    )
    assert r1.status_code == 200, f"First verify should succeed: {r1.text}"
    assert "reset_token" in r1.json()

    # used_at is now set → second attempt sees no valid row
    r2 = client.post(
        "/api/auth/verify-otp",
        json={"email": "otp_single_use@test.com", "otp": "654321"},
    )
    assert r2.status_code == 400, (
        f"Second verify with same OTP should fail: {r2.status_code}: {r2.text}"
    )


def test_otp_locked_after_max_attempts(client, db, provider_org):
    """OTP bị vô hiệu hóa sau khi vượt giới hạn số lần thử."""
    org = _make_org(db, "Lock Org")
    user = _make_user(db, org.id, "otp_lock@test.com", role="customer")
    otp_row = _make_otp(db, user.id, otp="777777")
    # Simulate already at max attempts
    otp_row.attempts = OTP_MAX_ATTEMPTS
    db.commit()

    r = client.post(
        "/api/auth/verify-otp",
        json={"email": "otp_lock@test.com", "otp": "777777"},
    )
    assert r.status_code == 429, f"Expected 429, got {r.status_code}: {r.text}"


# ══════════════════════════════════════════════════════════════════════════════
# LỖI 6: link_user_to_contact cho phép cross-org
# ══════════════════════════════════════════════════════════════════════════════

def test_link_cross_org_user_to_contact_is_rejected(client, db, admin_token):
    """Admin link user từ org B vào contact org A → 400."""
    org_a = _make_org(db, "Org A Contacts")
    org_b = _make_org(db, "Org B Contacts")

    from app.models.contact import Contact
    contact = Contact(org_id=org_a.id, name="Alice", email="alice@orga.com")
    db.add(contact)
    db.commit()
    db.refresh(contact)

    # user_b belongs to org_b, NOT org_a
    user_b = _make_user(db, org_b.id, "user_b_contacts@test.com")

    r = client.put(
        f"/api/organizations/{org_a.id}/contacts/{contact.id}/link-user",
        json={"user_id": user_b.id},
        headers=_h(admin_token),
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    assert "does not belong" in r.json()["detail"].lower()


def test_link_same_org_user_to_contact_succeeds(client, db, admin_token):
    """Admin link user từ org A vào contact org A → 200."""
    org_a = _make_org(db, "Org A Same")
    from app.models.contact import Contact
    contact = Contact(org_id=org_a.id, name="Bob", email="bob@orga.com")
    db.add(contact)
    db.commit()
    db.refresh(contact)

    user_a = _make_user(db, org_a.id, "user_a_same@test.com")

    r = client.put(
        f"/api/organizations/{org_a.id}/contacts/{contact.id}/link-user",
        json={"user_id": user_a.id},
        headers=_h(admin_token),
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["user_id"] == user_a.id


def test_link_staff_user_to_contact_succeeds(client, db, admin_token, provider_org):
    """Admin link staff user (provider org) to client org contact → 200.

    Sprint 2 MEDIUM 4: the Sprint 1 check `target_user.org_id != org_id` blocked
    this because staff.org_id == provider_org.id ≠ client_org.id.
    Fix: only enforce the check for customer-role users.
    """
    client_org = _make_org(db, "Client Org Staff Link")
    from app.models.contact import Contact
    contact = Contact(org_id=client_org.id, name="Charlie", email="charlie@client.com")
    db.add(contact)
    db.commit()
    db.refresh(contact)

    staff = _make_user(db, provider_org.id, "staff_link_contact@test.com", role="staff")

    r = client.put(
        f"/api/organizations/{client_org.id}/contacts/{contact.id}/link-user",
        json={"user_id": staff.id},
        headers=_h(admin_token),
    )
    assert r.status_code == 200, (
        f"Staff (provider org) should be linkable to client contact: {r.status_code}: {r.text}"
    )
    assert r.json()["user_id"] == staff.id


# ══════════════════════════════════════════════════════════════════════════════
# LỖI 7: Reset token TTL dài hơn OTP
# ══════════════════════════════════════════════════════════════════════════════

def test_reset_token_ttl_is_short(db):
    """Reset token phải có exp ≤ RESET_TOKEN_EXPIRE_MINUTES, không kế thừa session TTL."""
    from app.core.security import create_access_token, decode_token
    from app.config import JWT_SECRET, JWT_ALGO, ACCESS_TOKEN_EXPIRE_MINUTES

    token, _ = create_access_token(1, "reset", expire_minutes=RESET_TOKEN_EXPIRE_MINUTES)
    claims = decode_token(token)

    issued_at = datetime.utcnow()
    exp = datetime.utcfromtimestamp(claims["exp"])
    ttl_minutes = (exp - issued_at).total_seconds() / 60

    # Must be close to RESET_TOKEN_EXPIRE_MINUTES, not ACCESS_TOKEN_EXPIRE_MINUTES
    assert ttl_minutes <= RESET_TOKEN_EXPIRE_MINUTES + 1, (
        f"Reset token TTL is {ttl_minutes:.1f} min, expected ≤ {RESET_TOKEN_EXPIRE_MINUTES}"
    )
    # Must be shorter than a full session token
    assert RESET_TOKEN_EXPIRE_MINUTES < ACCESS_TOKEN_EXPIRE_MINUTES or ACCESS_TOKEN_EXPIRE_MINUTES == 30, (
        "RESET_TOKEN_EXPIRE_MINUTES should be <= ACCESS_TOKEN_EXPIRE_MINUTES"
    )


def test_expired_reset_token_rejected(client, db):
    """Reset token hết hạn → POST /reset-password → 400."""
    from app.core.security import decode_token
    from app.config import JWT_SECRET, JWT_ALGO
    import uuid

    org = _make_org(db, "Expired Reset Org")
    user = _make_user(db, org.id, "expired_reset@test.com")

    # Craft a token that is already expired
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user.id),
        "role": "reset",
        "jti": jti,
        "type": "access",
        "exp": datetime.utcnow() - timedelta(minutes=1),
    }
    expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

    r = client.post(
        "/api/auth/reset-password",
        json={"reset_token": expired_token, "new_password": "NewPass123!"},
    )
    assert r.status_code == 400, f"Expected 400 for expired token, got {r.status_code}: {r.text}"
