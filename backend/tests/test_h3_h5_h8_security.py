"""Security regression tests for H3 (transfer multi-assignee sync),
H5 (invoice negative amount validation), H8 (TESTING env bypass removed)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── helpers ────────────────────────────────────────────────────────────────────

def _org(db, name):
    from app.models.organization import Organization
    import uuid
    o = Organization(name=name, code=f"H-{uuid.uuid4().hex[:6].upper()}", status="active")
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _staff(db, org_id, email):
    from app.models.user import User
    from app.core.security import hash_password
    from app.models.team import StaffOrgAssignment
    u = User(org_id=org_id, email=email, full_name=email.split("@")[0],
             password_hash=hash_password("pass1234"), role="staff", is_active=True)
    db.add(u)
    db.flush()
    db.add(StaffOrgAssignment(user_id=u.id, org_id=org_id))
    db.commit()
    db.refresh(u)
    return u


def _ticket(db, org_id, assignee_id):
    from app.models.ticket import Ticket, TicketAssignee
    t = Ticket(org_id=org_id, subject="Transfer test", status="Open", priority="Medium",
               ticket_type="incident", raised_by_email="c@c.com", assignee_id=assignee_id)
    db.add(t)
    db.flush()
    db.add(TicketAssignee(ticket_id=t.id, user_id=assignee_id, is_primary=True,
                          assigned_by=assignee_id))
    db.commit()
    db.refresh(t)
    return t


def _transfer_request(db, ticket_id, from_id, to_id):
    from app.models.transfer_request import TicketTransferRequest
    req = TicketTransferRequest(ticket_id=ticket_id, from_staff_id=from_id, to_staff_id=to_id)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def _token(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ══════════════════════════════════════════════════════════════════════════════
# H3 — accept_transfer must sync TicketAssignee table via set_ticket_assignees
# ══════════════════════════════════════════════════════════════════════════════

def test_h3_accept_transfer_updates_ticket_assignee_table(db, client):
    """After accepting a transfer, TicketAssignee must reflect the new assignee."""
    from app.models.ticket import TicketAssignee

    org = _org(db, "H3Org")
    staff_a = _staff(db, org.id, "h3_staff_a@test.com")
    staff_b = _staff(db, org.id, "h3_staff_b@test.com")

    ticket = _ticket(db, org.id, staff_a.id)
    req = _transfer_request(db, ticket.id, staff_a.id, staff_b.id)

    # staff_b accepts
    tok_b = _token(client, "h3_staff_b@test.com")
    r = client.put(
        f"/api/tickets/{ticket.id}/transfer-request/{req.id}/accept",
        headers=_auth(tok_b),
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee_id"] == staff_b.id

    # Refresh session to see committed data
    db.expire_all()

    # ticket.assignee_id must be updated
    from app.models.ticket import Ticket
    updated_ticket = db.query(Ticket).filter(Ticket.id == ticket.id).first()
    assert updated_ticket.assignee_id == staff_b.id, "ticket.assignee_id not updated"

    # TicketAssignee table must have staff_b, not staff_a
    assignees = db.query(TicketAssignee).filter(
        TicketAssignee.ticket_id == ticket.id
    ).all()
    assignee_ids = {a.user_id for a in assignees}
    assert staff_b.id in assignee_ids, "staff_b not in TicketAssignee after transfer"
    assert staff_a.id not in assignee_ids, "staff_a still in TicketAssignee after transfer"


def test_h3_accept_transfer_only_target_can_accept(db, client):
    """Only the target staff (to_staff_id) can accept a transfer request."""
    org = _org(db, "H3bOrg")
    staff_a = _staff(db, org.id, "h3b_staff_a@test.com")
    staff_b = _staff(db, org.id, "h3b_staff_b@test.com")

    ticket = _ticket(db, org.id, staff_a.id)
    req = _transfer_request(db, ticket.id, staff_a.id, staff_b.id)

    # staff_a (the requester) tries to accept their own transfer — should be 403
    tok_a = _token(client, "h3b_staff_a@test.com")
    r = client.put(
        f"/api/tickets/{ticket.id}/transfer-request/{req.id}/accept",
        headers=_auth(tok_a),
    )
    assert r.status_code == 403, r.text


# ══════════════════════════════════════════════════════════════════════════════
# H5 — InvoiceLineIn must reject non-positive unit_price and quantity
# ══════════════════════════════════════════════════════════════════════════════

def test_h5_negative_unit_price_rejected(db, client, admin_user, admin_token, client_org):
    """POST /api/invoices with unit_price <= 0 must return 422."""
    r = client.post(
        "/api/invoices",
        headers=_auth(admin_token),
        json={
            "org_id": client_org.id,
            "lines": [{"description": "Bad item", "quantity": "1", "unit_price": "-500"}],
        },
    )
    assert r.status_code == 422, (
        f"Expected 422 for negative unit_price, got {r.status_code}: {r.text}"
    )


def test_h5_zero_unit_price_rejected(db, client, admin_user, admin_token, client_org):
    """unit_price = 0 must also be rejected."""
    r = client.post(
        "/api/invoices",
        headers=_auth(admin_token),
        json={
            "org_id": client_org.id,
            "lines": [{"description": "Zero item", "quantity": "1", "unit_price": "0"}],
        },
    )
    assert r.status_code == 422, (
        f"Expected 422 for zero unit_price, got {r.status_code}: {r.text}"
    )


def test_h5_negative_quantity_rejected(db, client, admin_user, admin_token, client_org):
    """quantity <= 0 must be rejected."""
    r = client.post(
        "/api/invoices",
        headers=_auth(admin_token),
        json={
            "org_id": client_org.id,
            "lines": [{"description": "Neg qty", "quantity": "-1", "unit_price": "100000"}],
        },
    )
    assert r.status_code == 422, (
        f"Expected 422 for negative quantity, got {r.status_code}: {r.text}"
    )


def test_h5_positive_values_accepted(db, client, admin_user, admin_token, client_org):
    """Happy path: positive unit_price and quantity must succeed."""
    r = client.post(
        "/api/invoices",
        headers=_auth(admin_token),
        json={
            "org_id": client_org.id,
            "lines": [{"description": "Valid item", "quantity": "2", "unit_price": "50000"}],
        },
    )
    assert r.status_code == 201, (
        f"Expected 201 for valid invoice, got {r.status_code}: {r.text}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# H8 — TESTING env var must NOT bypass validate_production_config()
# ══════════════════════════════════════════════════════════════════════════════

def test_h8_testing_env_var_does_not_bypass_production_config():
    """Setting TESTING=true must NOT prevent validate_production_config from raising."""
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "ENV": "production",
        "JWT_SECRET": "changeme",   # insecure — should be caught
        "DATABASE_URL": "mysql+pymysql://u:p@db/app",
        "REDIS_HOST": "redis",
        "REDIS_PORT": "6379",
        "TESTING": "true",          # H8: this must NOT suppress the check
    }
    proc = subprocess.run(
        [sys.executable, "-c",
         "import app.config as c; c.validate_production_config()"],
        cwd=str(BACKEND_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0, (
        "validate_production_config() should fail for insecure JWT_SECRET "
        "even when TESTING=true is set in the environment"
    )
    assert "JWT_SECRET" in proc.stderr


def test_h8_testing_env_var_does_not_bypass_jwt_length_check():
    """Short JWT_SECRET must also fail even with TESTING=true in env."""
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "ENV": "production",
        "JWT_SECRET": "too-short",
        "DATABASE_URL": "mysql+pymysql://u:p@db/app",
        "REDIS_HOST": "redis",
        "REDIS_PORT": "6379",
        "TESTING": "true",
    }
    proc = subprocess.run(
        [sys.executable, "-c",
         "import app.config as c; c.validate_production_config()"],
        cwd=str(BACKEND_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "32 characters" in proc.stderr
