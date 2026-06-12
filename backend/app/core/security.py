# backend/app/core/security.py
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.config import JWT_SECRET, JWT_ALGO, ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_token(token: str) -> str:
    """SHA-256 hex digest — used to store refresh tokens in DB without plaintext."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int, role: str) -> tuple[str, str]:
    """Return (encoded_jwt, jti). jti is a UUID4 string identifying this specific token."""
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    return token, jti


def create_refresh_token(user_id: int) -> str:
    """Return an opaque random string (not a JWT). Store its hash in DB."""
    return secrets.token_urlsafe(32)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


def blacklist_user_tokens(user_id: int, redis_client) -> None:
    """Block all tokens for this user for 7 days (max refresh token lifetime)."""
    from app.config import REFRESH_TOKEN_EXPIRE_DAYS
    ttl = REFRESH_TOKEN_EXPIRE_DAYS * 86400
    redis_client.set(f"blacklist:user:{user_id}", "1", ex=ttl)


def is_user_blacklisted(user_id: int, redis_client) -> bool:
    return redis_client.exists(f"blacklist:user:{user_id}") > 0


def remove_user_from_blacklist(user_id: int, redis_client) -> None:
    redis_client.delete(f"blacklist:user:{user_id}")
