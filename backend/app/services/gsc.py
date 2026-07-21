"""
Google Search Console OAuth2 + API helpers.

Uses httpx (already a project dependency) — no google-api-python-client needed.
All Google token values are kept out of logs; callers must not log the return
values of exchange_code() or refresh_access_token() directly.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx

from app import config
from app.core.token_crypto import decrypt_secret, encrypt_secret

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
_GSC_SA_BASE = "https://searchconsole.googleapis.com/webmasters/v3/sites"
_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def build_auth_url(state: str) -> str:
    """Return the Google OAuth2 consent URL."""
    params = {
        "client_id": config.GSC_CLIENT_ID,
        "redirect_uri": config.GSC_REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    if not config.GOOGLE_INTEGRATIONS_ENABLED:
        raise RuntimeError("Google integrations disabled by runtime configuration")
    """Exchange an authorization code for access + refresh tokens.

    Returns the raw token dict from Google. NEVER log this dict.
    Raises httpx.HTTPStatusError on failure.
    """
    resp = httpx.post(_GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": config.GSC_CLIENT_ID,
        "client_secret": config.GSC_CLIENT_SECRET,
        "redirect_uri": config.GSC_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(conn) -> str:
    if not config.GOOGLE_INTEGRATIONS_ENABLED:
        raise RuntimeError("Google integrations disabled by runtime configuration")
    """Refresh the access token and update conn in-place (caller must commit).

    Returns the new access_token string. NEVER log it.
    Raises httpx.HTTPStatusError on failure.
    """
    resp = httpx.post(_GOOGLE_TOKEN_URL, data={
        "refresh_token": decrypt_secret(conn.refresh_token) or "",
        "client_id": config.GSC_CLIENT_ID,
        "client_secret": config.GSC_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    conn.access_token = encrypt_secret(data["access_token"])
    expires_in = int(data.get("expires_in", 3600))
    conn.token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)
    return decrypt_secret(conn.access_token) or conn.access_token


def get_valid_token(conn, db) -> str:
    """Return a valid access token, refreshing via refresh_token if expired.

    Updates conn.access_token and conn.token_expiry in DB if a refresh occurs.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if (
        conn.access_token
        and conn.token_expiry
        and conn.token_expiry > now + timedelta(minutes=2)
    ):
        return decrypt_secret(conn.access_token) or conn.access_token
    token = refresh_access_token(conn)
    db.add(conn)
    db.commit()
    return token


def list_sites(access_token: str) -> list:
    if not config.GOOGLE_INTEGRATIONS_ENABLED:
        raise RuntimeError("Google integrations disabled by runtime configuration")
    """Return list of verified GSC site entries for the connected account."""
    resp = httpx.get(
        _GSC_SITES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("siteEntry", [])


def query_search_analytics(access_token: str, site_url: str, payload: dict) -> dict:
    if not config.GOOGLE_INTEGRATIONS_ENABLED:
        raise RuntimeError("Google integrations disabled by runtime configuration")
    """Run a searchAnalytics.query request and return the raw GSC response."""
    url = f"{_GSC_SA_BASE}/{quote(site_url, safe='')}/searchAnalytics/query"
    resp = httpx.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def revoke_token(token: str) -> None:
    if not config.GOOGLE_INTEGRATIONS_ENABLED:
        return
    """Revoke a Google OAuth token (best-effort; errors are silently ignored)."""
    token = decrypt_secret(token) or token
    try:
        httpx.post(_GOOGLE_REVOKE_URL, params={"token": token}, timeout=5)
    except Exception:
        pass
