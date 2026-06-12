"""Regression tests for production hardening and cross-org access."""
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_invoice(db, org_id, status="sent"):
    from app.models.invoice import Invoice, InvoiceLine, generate_invoice_number

    inv = Invoice(
        invoice_number=generate_invoice_number(db, date.today().year),
        org_id=org_id,
        status=status,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        subtotal=Decimal("100000"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("10000"),
        total=Decimal("110000"),
    )
    db.add(inv)
    db.flush()
    db.add(InvoiceLine(
        invoice_id=inv.id,
        description="Service",
        quantity=Decimal("1"),
        unit_price=Decimal("100000"),
        line_total=Decimal("100000"),
    ))
    db.commit()
    db.refresh(inv)
    return inv


def _make_subscription(db, org_id):
    from app.models.subscription import Subscription

    sub = Subscription(
        org_id=org_id,
        status="active",
        start_date=date.today(),
        current_period_start=date.today(),
        current_period_end=date.today() + timedelta(days=30),
        billing_cycle="monthly",
        next_billing_date=date.today() + timedelta(days=30),
        unit_price=Decimal("100000"),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _make_ticket(db, org_id, raised_by_id=None):
    from app.models.ticket import Ticket

    ticket = Ticket(
        org_id=org_id,
        subject="Attachment scoped ticket",
        description="desc",
        status="Open",
        priority="Medium",
        ticket_type="question",
        raised_by=raised_by_id,
        raised_by_email="customer@test.com",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def test_production_config_rejects_missing_database_url(monkeypatch):
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "ENV": "production",
        "JWT_SECRET": "x" * 32,
        "DATABASE_URL": "",
        "DB_URL": "",
        "REDIS_HOST": "redis",
        "REDIS_PORT": "6379",
        "SMTP_PASS": "smtp",
        "IMAP_PASS": "imap",
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import app.config as c; c.validate_production_config()"],
        cwd=str(BACKEND_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "DATABASE_URL or DB_URL" in proc.stderr


@pytest.mark.parametrize(
    ("jwt_secret", "expected"),
    [
        ("", "JWT_SECRET must be set"),
        ("changeme", "JWT_SECRET must be set"),
        ("short-secret", "at least 32 characters"),
    ],
)
def test_production_config_rejects_insecure_jwt_secret(jwt_secret, expected):
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "ENV": "production",
        "JWT_SECRET": jwt_secret,
        "DATABASE_URL": "mysql+pymysql://u:p@db/app",
        "DB_URL": "",
        "REDIS_HOST": "redis",
        "REDIS_PORT": "6379",
        "SMTP_PASS": "smtp",
        "IMAP_PASS": "imap",
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import app.config as c; c.validate_production_config()"],
        cwd=str(BACKEND_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert expected in proc.stderr


def test_production_config_rejects_missing_redis_config():
    env = {
        key: value
        for key, value in {
            **os.environ,
            "PYTHONPATH": str(BACKEND_DIR),
            "ENV": "production",
            "JWT_SECRET": "x" * 32,
            "DATABASE_URL": "mysql+pymysql://u:p@db/app",
            "DB_URL": "",
            "SMTP_PASS": "smtp",
            "IMAP_PASS": "imap",
        }.items()
        if key not in {"REDIS_URL", "REDIS_HOST", "REDIS_PORT"}
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import app.config as c; c.validate_production_config()"],
        cwd=str(BACKEND_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "REDIS_URL or REDIS_HOST/REDIS_PORT" in proc.stderr


def test_production_config_rejects_missing_email_credentials_when_enabled():
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "ENV": "production",
        "JWT_SECRET": "x" * 32,
        "DATABASE_URL": "mysql+pymysql://u:p@db/app",
        "DB_URL": "",
        "REDIS_HOST": "redis",
        "REDIS_PORT": "6379",
        "EMAIL_FEATURES_ENABLED": "true",
        "SMTP_PASS": "",
        "IMAP_PASS": "",
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import app.config as c; c.validate_production_config()"],
        cwd=str(BACKEND_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "email features are enabled" in proc.stderr
    assert "IMAP_PASS" in proc.stderr
    assert "SMTP_PASS" in proc.stderr


def test_production_config_rejects_wildcard_cors(monkeypatch):
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "ENV": "production",
        "JWT_SECRET": "x" * 32,
        "DATABASE_URL": "mysql+pymysql://u:p@db/app",
        "DB_URL": "",
        "REDIS_HOST": "redis",
        "REDIS_PORT": "6379",
        "CORS_ORIGINS": "*",
        "SMTP_PASS": "smtp",
        "IMAP_PASS": "imap",
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import app.config as c; c.validate_production_config()"],
        cwd=str(BACKEND_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "CORS_ORIGINS" in proc.stderr


def test_customer_cross_org_invoice_detail_and_pdf_return_404(
    client, db, second_client_org, customer_token
):
    inv = _make_invoice(db, second_client_org.id)

    detail = client.get(f"/api/invoices/{inv.id}", headers=auth(customer_token))
    pdf = client.get(f"/api/invoices/{inv.id}/pdf", headers=auth(customer_token))

    assert detail.status_code == 404
    assert pdf.status_code == 404


def test_customer_cross_org_subscription_detail_returns_404(
    client, db, second_client_org, customer_token
):
    sub = _make_subscription(db, second_client_org.id)

    r = client.get(f"/api/subscriptions/{sub.id}", headers=auth(customer_token))

    assert r.status_code == 404


def test_customer_service_list_excludes_other_org_service(
    client, db, service, second_client_org, customer_token
):
    from app.models.service import Service

    other = Service(org_id=second_client_org.id, name="Other Org Service", type="saas", status="active")
    db.add(other)
    db.commit()

    r = client.get("/api/services", headers=auth(customer_token))

    assert r.status_code == 200
    names = {item["name"] for item in r.json()}
    assert service.name in names
    assert other.name not in names


def test_cross_org_attachment_download_returns_404(
    client, db, tmp_path, monkeypatch, second_client_org, customer_user, customer_token
):
    from app.models.attachment import TicketAttachment
    import app.config as cfg

    monkeypatch.setattr(cfg, "FILES_ROOT", str(tmp_path))
    ticket = _make_ticket(db, second_client_org.id)
    rel_path = "safe/file.txt"
    abs_path = tmp_path / rel_path
    abs_path.parent.mkdir(parents=True)
    abs_path.write_text("secret")
    attachment = TicketAttachment(
        ticket_id=ticket.id,
        file_name="file.txt",
        file_path=rel_path,
        file_size=6,
        mime_type="text/plain",
        detected_mime="text/plain",
        sha256="x" * 64,
        uploaded_by=customer_user.id,
    )
    db.add(attachment)
    db.commit()

    r = client.get(f"/api/attachments/{attachment.id}/download", headers=auth(customer_token))

    assert r.status_code == 404


def test_notification_mark_read_other_user_returns_404(
    client, db, staff_user, customer_token
):
    from app.models.notification import Notification

    notif = Notification(user_id=staff_user.id, title="Hidden", content="Nope", type="info")
    db.add(notif)
    db.commit()
    db.refresh(notif)

    r = client.put(f"/api/notifications/{notif.id}/read", headers=auth(customer_token))

    assert r.status_code == 404


def test_staff_ticket_csv_is_scoped_to_assigned_org(
    client, db, client_org, second_client_org, staff_token, staff_assignment
):
    _make_ticket(db, client_org.id)
    hidden = _make_ticket(db, second_client_org.id)

    r = client.get("/api/analytics/tickets.csv", headers=auth(staff_token))

    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    returned_ids = {line.split(",", 1)[0] for line in r.text.splitlines()[1:] if line}
    assert str(hidden.id) not in returned_ids


def test_staff_ticket_analytics_json_is_scoped_to_assigned_org(
    client, db, client_org, second_client_org, staff_token, staff_assignment
):
    _make_ticket(db, client_org.id)
    _make_ticket(db, second_client_org.id)

    r = client.get("/api/analytics/tickets", headers=auth(staff_token))

    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_invoice_pdf_smoke_for_admin(client, db, client_org, admin_token):
    inv = _make_invoice(db, client_org.id)

    r = client.get(f"/api/invoices/{inv.id}/pdf", headers=auth(admin_token))

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_get_attachment_path_rejects_path_traversal(tmp_path, monkeypatch):
    import app.config as cfg
    from app.services.file_storage import get_attachment_path
    from fastapi import HTTPException

    monkeypatch.setattr(cfg, "FILES_ROOT", str(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        get_attachment_path("../secret.txt")
    assert exc_info.value.status_code == 400


def test_login_rate_limit(client, customer_user):
    for _ in range(10):
        r = client.post("/api/auth/login", json={"email": customer_user.email, "password": "wrong"})
        assert r.status_code == 401

    limited = client.post("/api/auth/login", json={"email": customer_user.email, "password": "wrong"})

    assert limited.status_code == 429


def test_ticket_creation_rate_limit(client, customer_token, client_org):
    for idx in range(20):
        r = client.post(
            "/api/tickets",
            headers=auth(customer_token),
            json={"org_id": client_org.id, "subject": f"Rate limited {idx}"},
        )
        assert r.status_code == 201, r.text

    limited = client.post(
        "/api/tickets",
        headers=auth(customer_token),
        json={"org_id": client_org.id, "subject": "Rate limited final"},
    )

    assert limited.status_code == 429
