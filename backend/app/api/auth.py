# backend/app/api/auth.py
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.models.login_history import LoginHistory
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, hash_password, is_user_blacklisted,
)
from app.core.deps import get_current_user
from app.core.redis_client import redis_client
from app.core.limiter import limiter
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse,
    MeResponse, ChangePasswordRequest,
)

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
        pass  # never fail a login because of history logging


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
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

    user.last_login_at = datetime.now(timezone.utc)
    _record_login(db, request, payload.email, "success", user_id=user.id)
    db.commit()

    data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(claims["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Blacklist check on refresh too
    if is_user_blacklisted(user_id, redis_client):
        raise HTTPException(status_code=401, detail="Account deactivated")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return AccessTokenResponse(access_token=create_access_token({"sub": str(user.id)}))


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    return {"message": "Logged out"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any logged-in user can change their own password."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}
