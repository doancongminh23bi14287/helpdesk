from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet | None:
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        return None
    return Fernet(key.encode())


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    if value.startswith(_PREFIX):
        return value
    return _PREFIX + fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    if not value.startswith(_PREFIX):
        return value
    payload = value[len(_PREFIX):]
    try:
        return fernet.decrypt(payload.encode()).decode()
    except InvalidToken:
        raise ValueError("Invalid encrypted token payload")
