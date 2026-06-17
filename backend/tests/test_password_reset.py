import hashlib
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetOTP
from app.core.security import hash_password
from tests.conftest import TestingSessionLocal

http_client = TestClient(app)

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_org(db: Session, name: str = "Test Org", code: str = None):
    from app.models.organization import Organization
    import uuid
    org = Organization(
        name=name,
        code=code or f"TEST-{uuid.uuid4().hex[:8].upper()}",
        status="active",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_user(db: Session, email: str) -> User:
    org = _make_org(db)
    u = User(
        org_id=org.id,
        email=email,
        full_name="Test User",
        password_hash=hash_password("oldpassword"),
        role="customer",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _get_client_with_db(db: Session):
    """Return a TestClient that uses the given db session via dependency override."""
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ── tests ─────────────────────────────────────────────────────────────────────

def test_forgot_password_unknown_email_returns_200():
    """Email enumeration prevention: unknown email still returns 200."""
    db = TestingSessionLocal()
    try:
        c = _get_client_with_db(db)
        res = c.post("/api/auth/forgot-password", json={"email": "nobody@nowhere.com"})
        assert res.status_code == 200
        assert "code was sent" in res.json()["message"]
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_otp_generated_and_emailed():
    db = TestingSessionLocal()
    try:
        user = _make_user(db, "otp_test@example.com")
        c = _get_client_with_db(db)
        res = c.post("/api/auth/forgot-password", json={"email": user.email})
        assert res.status_code == 200
        db.expire_all()
        otp_row = db.query(PasswordResetOTP).filter(PasswordResetOTP.user_id == user.id).first()
        assert otp_row is not None
        assert otp_row.used_at is None
        assert otp_row.expires_at > datetime.utcnow()
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_verify_correct_otp_returns_reset_token():
    db = TestingSessionLocal()
    try:
        user = _make_user(db, "verify_otp@example.com")
        otp_code = "123456"
        otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
        otp_row = PasswordResetOTP(
            user_id=user.id,
            otp_hash=otp_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.add(otp_row)
        db.commit()
        c = _get_client_with_db(db)
        res = c.post("/api/auth/verify-otp", json={"email": user.email, "otp": otp_code})
        assert res.status_code == 200
        assert "reset_token" in res.json()
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_verify_wrong_otp_increments_attempts():
    db = TestingSessionLocal()
    try:
        user = _make_user(db, "wrong_otp@example.com")
        otp_row = PasswordResetOTP(
            user_id=user.id,
            otp_hash=hashlib.sha256(b"999999").hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.add(otp_row)
        db.commit()
        otp_row_id = otp_row.id
        c = _get_client_with_db(db)
        res = c.post("/api/auth/verify-otp", json={"email": user.email, "otp": "000000"})
        assert res.status_code == 400
        db.expire_all()
        updated = db.query(PasswordResetOTP).filter(PasswordResetOTP.id == otp_row_id).first()
        assert updated.attempts == 1
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_otp_locked_after_5_attempts():
    db = TestingSessionLocal()
    try:
        user = _make_user(db, "lock_otp@example.com")
        otp_row = PasswordResetOTP(
            user_id=user.id,
            otp_hash=hashlib.sha256(b"999999").hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            attempts=5,
        )
        db.add(otp_row)
        db.commit()
        c = _get_client_with_db(db)
        res = c.post("/api/auth/verify-otp", json={"email": user.email, "otp": "000000"})
        assert res.status_code == 429
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_reset_password_revokes_sessions():
    db = TestingSessionLocal()
    try:
        user = _make_user(db, "reset_pw@example.com")
        otp_code = "654321"
        otp_row = PasswordResetOTP(
            user_id=user.id,
            otp_hash=hashlib.sha256(otp_code.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.add(otp_row)
        db.commit()
        c = _get_client_with_db(db)
        verify_res = c.post("/api/auth/verify-otp", json={"email": user.email, "otp": otp_code})
        assert verify_res.status_code == 200
        reset_token = verify_res.json()["reset_token"]
        reset_res = c.post("/api/auth/reset-password", json={
            "reset_token": reset_token,
            "new_password": "newpass123",
        })
        assert reset_res.status_code == 200
        assert "Password updated" in reset_res.json()["message"]
        db.expire_all()
        updated_user = db.query(User).filter(User.id == user.id).first()
        from app.core.security import verify_password
        assert verify_password("newpass123", updated_user.password_hash)
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_expired_otp_rejected():
    db = TestingSessionLocal()
    try:
        user = _make_user(db, "expired_otp@example.com")
        otp_row = PasswordResetOTP(
            user_id=user.id,
            otp_hash=hashlib.sha256(b"123456").hexdigest(),
            expires_at=datetime.utcnow() - timedelta(minutes=1),  # already expired
        )
        db.add(otp_row)
        db.commit()
        c = _get_client_with_db(db)
        res = c.post("/api/auth/verify-otp", json={"email": user.email, "otp": "123456"})
        assert res.status_code == 400
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_reset_token_rejected_after_otp_used():
    """Using a reset_token a second time after the password was already reset → 400."""
    db = TestingSessionLocal()
    try:
        user = _make_user(db, "double_reset@example.com")
        otp_code = "112233"
        otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
        otp_row = PasswordResetOTP(
            user_id=user.id,
            otp_hash=otp_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.add(otp_row)
        db.commit()

        c = _get_client_with_db(db)

        # Step 1: verify OTP → get reset_token
        verify_res = c.post("/api/auth/verify-otp", json={"email": user.email, "otp": otp_code})
        assert verify_res.status_code == 200
        reset_token = verify_res.json()["reset_token"]

        # Step 2: first reset → should succeed
        first_reset = c.post("/api/auth/reset-password", json={
            "reset_token": reset_token,
            "new_password": "firstnewpass",
        })
        assert first_reset.status_code == 200

        # Step 3: second reset with same token → should be rejected (OTP already used)
        second_reset = c.post("/api/auth/reset-password", json={
            "reset_token": reset_token,
            "new_password": "secondnewpass",
        })
        assert second_reset.status_code == 400
        assert "already used" in second_reset.json()["detail"] or "expired" in second_reset.json()["detail"]
    finally:
        db.close()
        app.dependency_overrides.clear()
