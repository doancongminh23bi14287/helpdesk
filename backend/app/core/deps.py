# backend/app/core/deps.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.core.security import decode_token, is_user_blacklisted
from app.core.redis_client import redis_client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        claims = decode_token(token)
        if claims.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(claims["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    # Check blacklist first (fast Redis check before DB)
    if is_user_blacklisted(user_id, redis_client):
        raise HTTPException(status_code=401, detail="Account deactivated")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account deactivated")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_staff_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Staff or admin access required")
    return user
