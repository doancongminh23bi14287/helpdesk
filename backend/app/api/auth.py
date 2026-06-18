# backend/app/api/auth.py
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.login_history import LoginHistory
from app.models.organization import Organization
from app.models.user_session import UserSession
from app.models.password_reset import PasswordResetOTP
from app.models.email_outbox import EmailOutbox
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, hash_password, hash_token,
    blacklist_user_tokens, is_user_blacklisted, remove_user_from_blacklist,
    mark_reset_token_used, is_reset_token_used,
)
from app.core.deps import get_current_user, oauth2_scheme
from app.core.redis_client import redis_client
from app.core.limiter import limiter
from app import config
from app.config import REFRESH_TOKEN_EXPIRE_DAYS
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse,
    MeResponse, ChangePasswordRequest, LogoutRequest, UpdateMeRequest,
)
from app.services.avatar_storage import (
    AvatarValidationError,
    safe_delete_avatar,
    validate_and_save_avatar,
)
from app.core.constants import OTP_LENGTH, OTP_EXPIRY_MINUTES, OTP_MAX_ATTEMPTS, RESET_TOKEN_EXPIRE_MINUTES


# Hex-ish palette used for fallback initials background. Mirrors the
# DashCode-theme COLOR_OPTIONS exposed by the frontend Profile page.
# The legacy values ("green", "purple", "gray") were dropped when the
# global palette tightened around amber + neutral slate.
_ALLOWED_AVATAR_COLORS = {"amber", "orange", "blue", "sky", "rose", "slate"}


def _serialize_me(user: User, db: Session) -> dict:
    """Build the safe profile response — never exposes avatar_path."""
    org = db.query(Organization).filter(Organization.id == user.org_id).first() if user.org_id else None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "org_id": user.org_id,
        "must_change_password": bool(user.must_change_password),
        "phone": user.phone,
        "org_name": org.name if org else None,
        "avatar_url": user.avatar_url,
        "avatar_color": user.avatar_color,
    }

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _record_login(db: Session, request: Request, email: str, status: str, user_id=None):
    """Insert a LoginHistory row — fire-and-forget, never raise."""
    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent", "")[:255]
        entry = LoginHistory(
            user_id=user_id,
            email=email[:255],
            ip_address=ip,
            user_agent=ua,
            status=status,
        )
        db.add(entry)
        db.flush()
    except Exception:
        pass


def _revoke_all_sessions(user_id: int, db: Session) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_active.is_(True),
    ).update({"is_active": False, "revoked_at": now})


@router.post("/login", response_model=TokenResponse)
@limiter.limit(config.RATE_LIMIT_LOGIN)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        _record_login(db, request, payload.email, "failed")
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        _record_login(db, request, payload.email, "blocked", user_id=user.id)
        db.commit()
        raise HTTPException(status_code=401, detail="Account deactivated")

    if not verify_password(payload.password, user.password_hash):
        _record_login(db, request, payload.email, "failed", user_id=user.id)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    remove_user_from_blacklist(user.id, redis_client)
    user.last_login_at = datetime.now(timezone.utc)
    _record_login(db, request, payload.email, "success", user_id=user.id)

    access_token, jti = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:255]
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        current_jti=jti,
        ip_address=ip,
        user_agent=ua,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(session)
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
@limiter.limit(config.RATE_LIMIT_REFRESH)
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == token_hash,
    ).with_for_update().first()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Reuse detection: if session is already revoked, an attacker has the old token
    if not session.is_active:
        # Revoke all sessions for this user — token theft assumed
        _revoke_all_sessions(session.user_id, db)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token already used")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if session.expires_at < now:
        session.is_active = False
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Blacklist check (covers admin-forced deactivation)
    if is_user_blacklisted(session.user_id, redis_client):
        session.is_active = False
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Account deactivated")

    user = db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()
    if not user:
        session.is_active = False
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotate: revoke old session, create new session with fresh tokens
    session.is_active = False
    session.revoked_at = now

    new_access_token, new_jti = create_access_token(user.id, user.role)
    new_refresh_token = create_refresh_token(user.id)
    new_expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:255]

    new_session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(new_refresh_token),
        current_jti=new_jti,
        ip_address=ip,
        user_agent=ua,
        expires_at=new_expires_at,
        is_active=True,
    )
    db.add(new_session)
    db.commit()

    return AccessTokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=MeResponse)
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _serialize_me(user, db)


@router.patch("/me", response_model=MeResponse)
def update_me(
    payload: UpdateMeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Self-service profile updates.

    Forbidden fields (email, role, org_id, is_active, password_hash) are
    blocked by the schema's ``extra='forbid'`` — they will trigger 422
    rather than silently ignored.
    """
    changes = payload.model_dump(exclude_unset=True)

    if "full_name" in changes:
        name = (changes["full_name"] or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="full_name cannot be empty")
        user.full_name = name[:200]

    if "phone" in changes:
        phone = changes["phone"]
        user.phone = phone.strip()[:50] if phone else None

    if "avatar_color" in changes:
        color = changes["avatar_color"]
        if color is not None and color not in _ALLOWED_AVATAR_COLORS:
            raise HTTPException(
                status_code=422,
                detail=f"avatar_color must be one of {sorted(_ALLOWED_AVATAR_COLORS)}",
            )
        user.avatar_color = color

    db.commit()
    db.refresh(user)
    return _serialize_me(user, db)


@router.post("/me/avatar", response_model=MeResponse)
@limiter.limit("10/minute")
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a new avatar for the current user."""
    file_data = file.file.read()
    try:
        result = validate_and_save_avatar(
            file_data=file_data,
            declared_mime=file.content_type,
            user_id=user.id,
        )
    except AvatarValidationError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)

    old_path = user.avatar_path
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    user.avatar_path = result["stored_path"]
    user.avatar_mime_type = result["mime_type"]
    user.avatar_size_bytes = result["file_size"]
    user.avatar_updated_at = now
    # Public-by-UUID URL so <img src> works without an Authorization header.
    # The UUID-named filename is unguessable; resolve_path on the server side
    # blocks path traversal, and a DB lookup ties the URL back to the owning
    # user before any bytes are served.
    user.avatar_url = _public_avatar_url(user.id, result["stored_path"], now)

    db.commit()

    if old_path and old_path != result["stored_path"]:
        safe_delete_avatar(old_path)

    db.refresh(user)
    return _serialize_me(user, db)


@router.delete("/me/avatar", response_model=MeResponse)
def delete_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove the current user's avatar. ``avatar_color`` is preserved."""
    old_path = user.avatar_path

    user.avatar_url = None
    user.avatar_path = None
    user.avatar_mime_type = None
    user.avatar_size_bytes = None
    user.avatar_updated_at = None
    db.commit()

    if old_path:
        safe_delete_avatar(old_path)

    db.refresh(user)
    return _serialize_me(user, db)


@router.get("/avatars/{user_id}/{filename}")
def serve_public_avatar(
    user_id: int,
    filename: str,
    db: Session = Depends(get_db),
):
    """Stream an avatar by its UUID filename.

    Auth-free so ``<img src>`` works in the browser. Privacy depends on the
    unguessable UUID filename; the DB row must agree the file belongs to the
    requested user, and ``resolve_path`` rejects any path-traversal attempt.
    """
    from app.services.storage import get_storage_backend

    rel_path = f"avatars/{user_id}/{filename}"
    user = (
        db.query(User)
        .filter(User.id == user_id, User.avatar_path == rel_path)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Avatar not found")

    path = get_storage_backend().resolve_path(rel_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Avatar file missing")

    return FileResponse(
        path,
        media_type=user.avatar_mime_type or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=300"},
    )


def _public_avatar_url(user_id: int, stored_path: str, when) -> str:
    # stored_path looks like ``avatars/{user_id}/{uuid}.{ext}`` — strip the
    # ``avatars/{user_id}/`` prefix so the URL only exposes the UUID filename.
    prefix = f"avatars/{user_id}/"
    filename = stored_path[len(prefix):] if stored_path.startswith(prefix) else stored_path
    cache_buster = int(when.timestamp()) if when else 0
    return f"/api/auth/avatars/{user_id}/{filename}?v={cache_buster}"


@router.post("/logout")
def logout(
    payload: LogoutRequest | None = Body(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if payload and payload.refresh_token:
        token_hash = hash_token(payload.refresh_token)
        session = db.query(UserSession).filter(
            UserSession.refresh_token_hash == token_hash,
            UserSession.user_id == user.id,
            UserSession.is_active.is_(True),
        ).first()
        if session:
            session.is_active = False
            session.revoked_at = now
            db.commit()
    else:
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_active.is_(True),
        ).update({"is_active": False, "revoked_at": now})
        db.commit()
    return {"message": "Logged out"}


@router.get("/sessions")
def list_sessions(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the current user's tracked sessions without exposing refresh tokens."""
    claims = decode_token(token)
    current_jti = claims.get("jti")
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .order_by(UserSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "revoked_at": s.revoked_at,
            "is_active": s.is_active,
            "is_current": bool(current_jti and s.current_jti == current_jti),
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.is_active:
        session.is_active = False
        session.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    return {"message": "Session revoked"}


@router.post("/logout-all")
def logout_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _revoke_all_sessions(user.id, db)
    db.commit()
    blacklist_user_tokens(user.id, redis_client)
    return {"message": "All sessions revoked"}


@router.post("/change-password")
@limiter.limit(config.RATE_LIMIT_CHANGE_PASSWORD)
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any logged-in user can change their own password. Revokes all sessions."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    _revoke_all_sessions(current_user.id, db)
    blacklist_user_tokens(current_user.id, redis_client)
    db.commit()
    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    email = (payload.get("email") or "").strip().lower()
    # Always return 200 to prevent email enumeration
    generic_ok = {"message": "If that email exists, a code was sent"}

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        return generic_ok

    # Invalidate any existing unused OTPs for this user
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id,
        PasswordResetOTP.used_at.is_(None),
    ).update({"used_at": datetime.utcnow()})

    # Generate 6-digit OTP
    otp = f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"
    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    otp_row = PasswordResetOTP(
        user_id=user.id,
        otp_hash=otp_hash,
        expires_at=expires_at,
    )
    db.add(otp_row)

    # Queue email
    body_text = (
        f"Your CustomerHub password reset code is: {otp}. "
        f"It expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
        f"Mã đặt lại mật khẩu của bạn là: {otp}, hết hạn sau {OTP_EXPIRY_MINUTES} phút."
    )
    body_html = (
        f"<p>Your CustomerHub password reset code is: <strong>{otp}</strong>. "
        f"It expires in {OTP_EXPIRY_MINUTES} minutes.</p>"
        f"<p>Mã đặt lại mật khẩu của bạn là: <strong>{otp}</strong>, hết hạn sau {OTP_EXPIRY_MINUTES} phút.</p>"
    )
    email_row = EmailOutbox(
        email_type="password_reset",
        recipient_email=user.email,
        recipient_name=user.full_name,
        subject="CustomerHub — Password Reset Code",
        body_text=body_text,
        body_html=body_html,
        status="pending",
        scheduled_at=datetime.utcnow(),
    )
    db.add(email_row)
    db.commit()

    return generic_ok


@router.post("/verify-otp")
def verify_otp(payload: dict = Body(...), db: Session = Depends(get_db)):
    email = (payload.get("email") or "").strip().lower()
    otp_input = str(payload.get("otp") or "").strip()

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    now = datetime.utcnow()
    # with_for_update() emits SELECT ... FOR UPDATE — the row is locked for the
    # duration of this transaction so concurrent requests cannot both read the
    # same attempt count and bypass the brute-force limit.
    otp_row = (
        db.query(PasswordResetOTP)
        .filter(
            PasswordResetOTP.user_id == user.id,
            PasswordResetOTP.used_at.is_(None),
            PasswordResetOTP.expires_at > now,
        )
        .order_by(PasswordResetOTP.created_at.desc())
        .with_for_update()
        .first()
    )
    if not otp_row:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Check attempt count before verifying
    if otp_row.attempts >= OTP_MAX_ATTEMPTS:
        otp_row.used_at = now  # invalidate
        db.commit()
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new code.")

    otp_row.attempts += 1
    db.flush()

    expected_hash = hashlib.sha256(otp_input.encode()).hexdigest()
    if otp_row.otp_hash != expected_hash:
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Mark the OTP as consumed in the same transaction as token issuance.
    # Without this, a second concurrent verify with the same correct OTP would also
    # pass (it would find used_at=NULL after the FOR UPDATE lock releases) and get
    # its own reset token — two valid tokens for one OTP.
    otp_row.used_at = now
    reset_token, _ = create_access_token(user.id, "reset", expire_minutes=RESET_TOKEN_EXPIRE_MINUTES)
    db.commit()
    return {"reset_token": reset_token}


@router.post("/reset-password")
def reset_password_via_otp(payload: dict = Body(...), db: Session = Depends(get_db)):
    reset_token = payload.get("reset_token") or ""
    new_password = payload.get("new_password") or ""

    try:
        claims = decode_token(reset_token)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if claims.get("role") != "reset":
        raise HTTPException(status_code=400, detail="Invalid token type")

    user_id = int(claims.get("sub", 0))
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    jti = claims.get("jti", "")
    if not jti or is_reset_token_used(jti, redis_client):
        raise HTTPException(status_code=400, detail="Reset token already used or expired. Please start over.")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    mark_reset_token_used(jti, redis_client, RESET_TOKEN_EXPIRE_MINUTES)

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    _revoke_all_sessions(user_id, db)
    blacklist_user_tokens(user_id, redis_client)
    db.commit()

    return {"message": "Password updated. Please log in."}
