"""Sprint 4 Security Tests — scope_tickets enforcement, OTP rate limits, /ready sanitization."""
import hashlib
import pytest
from datetime import datetime, timedelta


# ─── helpers ──────────────────────────────────────────────────────────────────

def _org(db, name, code=None):
    from app.models.organization import Organization
    import uuid
    o = Organization(name=name, code=code or f"S4-{uuid.uuid4().hex[:6].upper()}", status="active")
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


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _project(db, org_id, created_by, visibility="customer_visible"):
    from app.models.project import Project
    import uuid
    p = Project(org_id=org_id, name=f"Proj-{uuid.uuid4().hex[:4]}",
                project_type="seo", status="open", visibility=visibility,
                created_by=created_by, progress_percent=0)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _ticket(db, org_id, raised_by, project_id=None, subject="Test Ticket"):
    from app.models.ticket import Ticket
    t = Ticket(org_id=org_id, subject=subject, status="Open", priority="Medium",
               ticket_type="incident", raised_by=raised_by, raised_by_email="x@x.com",
               project_id=project_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _reply(db, ticket_id, author_id, content="Hello"):
    from app.models.ticket import TicketReply
    r = TicketReply(ticket_id=ticket_id, author_id=author_id, content=content,
                    is_internal=False, source="portal")
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ══════════════════════════════════════════════════════════════════════════════
# M14 — list_project_tickets: customer cannot see other customers' tickets
# ══════════════════════════════════════════════════════════════════════════════

def test_m14_customer_cannot_see_other_customers_tickets_via_project(db, client, admin_user):
    """After scope_tickets fix: customer B cannot see customer A's tickets via project endpoint."""
    org = _org(db, "M14Org")
    project = _project(db, org.id, admin_user.id)

    cust_a = _user(db, org.id, "m14_cust_a@test.com")
    cust_b = _user(db, org.id, "m14_cust_b@test.com")

    # A raises a ticket linked to the project
    _ticket(db, org.id, cust_a.id, project_id=project.id, subject="A's private ticket")

    tok_b = _token(client, "m14_cust_b@test.com")
    r = client.get(f"/api/projects/{project.id}/tickets", headers=_auth(tok_b))
    assert r.status_code == 200, r.text
    subjects = [t["subject"] for t in r.json()]
    assert "A's private ticket" not in subjects, "Customer B must not see Customer A's ticket"


def test_m14_customer_sees_own_tickets_via_project(db, client, admin_user):
    """Happy path: customer sees their OWN tickets via project endpoint."""
    org = _org(db, "M14bOrg")
    project = _project(db, org.id, admin_user.id)
    cust = _user(db, org.id, "m14_own@test.com")

    _ticket(db, org.id, cust.id, project_id=project.id, subject="My own ticket")

    tok = _token(client, "m14_own@test.com")
    r = client.get(f"/api/projects/{project.id}/tickets", headers=_auth(tok))
    assert r.status_code == 200, r.text
    subjects = [t["subject"] for t in r.json()]
    assert "My own ticket" in subjects


# ══════════════════════════════════════════════════════════════════════════════
# M15 — project discussion: customer cannot read/write to other's ticket
# ══════════════════════════════════════════════════════════════════════════════

def test_m15_customer_cannot_read_other_customers_discussion(db, client, admin_user):
    """GET /discussion: customer B cannot see replies on customer A's ticket."""
    org = _org(db, "M15rOrg")
    project = _project(db, org.id, admin_user.id)

    cust_a = _user(db, org.id, "m15_read_a@test.com")
    cust_b = _user(db, org.id, "m15_read_b@test.com")

    ticket_a = _ticket(db, org.id, cust_a.id, project_id=project.id, subject="A's discussion ticket")
    _reply(db, ticket_a.id, cust_a.id, content="A's reply content")

    tok_b = _token(client, "m15_read_b@test.com")
    r = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(tok_b))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert all(item["ticket_id"] != ticket_a.id for item in items), \
        "Customer B must not see replies from Customer A's ticket"


def test_m15_customer_sees_own_discussion(db, client, admin_user):
    """Happy path: customer sees replies on THEIR OWN ticket in discussion."""
    org = _org(db, "M15ownOrg")
    project = _project(db, org.id, admin_user.id)
    cust = _user(db, org.id, "m15_own@test.com")

    ticket = _ticket(db, org.id, cust.id, project_id=project.id)
    _reply(db, ticket.id, cust.id, content="My own reply")

    tok = _token(client, "m15_own@test.com")
    r = client.get(f"/api/projects/{project.id}/discussion", headers=_auth(tok))
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1


def test_m15_customer_cannot_post_to_other_customers_ticket_via_discussion(db, client, admin_user):
    """POST /discussion: customer B has no open ticket → 409, cannot post to A's ticket."""
    org = _org(db, "M15pOrg")
    project = _project(db, org.id, admin_user.id)

    cust_a = _user(db, org.id, "m15_post_a@test.com")
    cust_b = _user(db, org.id, "m15_post_b@test.com")

    # Only A has a ticket linked to the project
    _ticket(db, org.id, cust_a.id, project_id=project.id)

    tok_b = _token(client, "m15_post_b@test.com")
    r = client.post(
        f"/api/projects/{project.id}/discussion",
        json={"content": "injected by B"},
        headers=_auth(tok_b),
    )
    # B has no open ticket → 409 (not 200 posting into A's ticket)
    assert r.status_code == 409, \
        f"Expected 409 (no ticket for B), got {r.status_code}: {r.text}"


# ══════════════════════════════════════════════════════════════════════════════
# H1 / H2 — Rate limit on /verify-otp and /reset-password
# ══════════════════════════════════════════════════════════════════════════════

def test_h1_verify_otp_rate_limited_after_5_attempts(db, client):
    """/verify-otp must return 429 after 5 requests per minute (brute-force protection)."""
    payload = {"email": "h1_rl_exhaust@test.com", "otp": "000000"}
    # First 5 requests: within limit (400 = bad OTP, but not 429)
    for i in range(5):
        r = client.post("/api/auth/verify-otp", json=payload)
        assert r.status_code != 429, f"Hit rate limit too early on request #{i+1}"
    # 6th request: must be rate-limited
    r = client.post("/api/auth/verify-otp", json=payload)
    assert r.status_code == 429, (
        f"Expected 429 after 5 OTP attempts, got {r.status_code}. "
        "If this is 400, @limiter.limit(config.RATE_LIMIT_OTP_VERIFY) is not applied."
    )


def test_h2_reset_password_rate_limited_after_5_attempts(db, client):
    """/reset-password must return 429 after 5 requests per minute."""
    payload = {"reset_token": "invalid_token_h2_rl", "new_password": "newpass99"}
    for i in range(5):
        r = client.post("/api/auth/reset-password", json=payload)
        assert r.status_code != 429, f"Hit rate limit too early on request #{i+1}"
    r = client.post("/api/auth/reset-password", json=payload)
    assert r.status_code == 429, (
        f"Expected 429 after 5 reset attempts, got {r.status_code}. "
        "If this is 400, @limiter.limit(config.RATE_LIMIT_OTP_RESET) is not applied."
    )


# ══════════════════════════════════════════════════════════════════════════════
# M16 — /ready must not leak SMTP credentials
# ══════════════════════════════════════════════════════════════════════════════

def test_m16_ready_endpoint_does_not_leak_smtp_credentials(client):
    """GET /ready must not expose SMTP user, host, port, or password in response."""
    r = client.get("/ready")
    assert r.status_code in (200, 503)

    body = r.json()
    body_str = str(body)

    # smtp_config must be exactly "ok" or "error" — no credential detail
    checks = body.get("checks", {})
    smtp_val = checks.get("smtp_config", "")
    assert smtp_val in ("ok", "error"), (
        f"smtp_config should be 'ok' or 'error', got: {smtp_val!r}"
    )

    # No '@' or ':N' patterns that would indicate email or host:port
    assert "@" not in smtp_val, "SMTP user/email must not appear in /ready response"
    assert smtp_val.count(":") == 0, "SMTP host:port must not appear in /ready response"


def test_m16_ready_db_and_redis_errors_sanitized(client):
    """DB/Redis error messages must not leak connection strings."""
    r = client.get("/ready")
    checks = r.json().get("checks", {})

    # Errors must be bare "error" strings, not exception details with URLs/passwords
    for key in ("database", "redis"):
        val = checks.get(key, "ok")
        if val != "ok":
            assert val == "error", (
                f"checks['{key}'] should be 'ok' or 'error', not: {val!r}"
            )
