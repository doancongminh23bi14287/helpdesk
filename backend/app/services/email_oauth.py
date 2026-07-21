"""OAuth helpers for reconnecting the Gmail outbound sender."""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app import config

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPES = "openid email https://www.googleapis.com/auth/gmail.send"


def build_auth_url(state: str) -> str:
    params = {
        "client_id": config.GSC_CLIENT_ID,
        "redirect_uri": config.GSC_REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    response = httpx.post(
        _TOKEN_URL,
        data={
            "code": code,
            "client_id": config.GSC_CLIENT_ID,
            "client_secret": config.GSC_CLIENT_SECRET,
            "redirect_uri": config.GSC_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def token_expiry(tokens: dict) -> datetime:
    expires_in = int(tokens.get("expires_in", 3600))
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)
