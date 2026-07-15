"""Google Analytics 4 — OAuth2 + Data API helpers."""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app import config
from app.core.token_crypto import decrypt_secret, encrypt_secret

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_GA4_ADMIN_URL = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"
_GA4_DATA_URL = "https://analyticsdata.googleapis.com/v1beta/properties"
_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def build_auth_url(state: str) -> str:
    params = {
        "client_id": config.GSC_CLIENT_ID,
        "redirect_uri": config.GA4_REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    resp = httpx.post(_GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": config.GSC_CLIENT_ID,
        "client_secret": config.GSC_CLIENT_SECRET,
        "redirect_uri": config.GA4_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(conn) -> str:
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


def list_properties(access_token: str) -> list:
    """Return list of GA4 properties from accountSummaries."""
    resp = httpx.get(
        _GA4_ADMIN_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    props = []
    for account in data.get("accountSummaries", []):
        for prop in account.get("propertySummaries", []):
            props.append({
                "property": prop.get("property", ""),
                "displayName": prop.get("displayName", ""),
                "account": account.get("displayName", ""),
            })
    return props


def run_report(access_token: str, property_id: str, payload: dict) -> dict:
    """Run a GA4 Data API report."""
    url = f"{_GA4_DATA_URL}/{property_id}:runReport"
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
    try:
        httpx.post(_GOOGLE_REVOKE_URL, params={"token": token}, timeout=5)
    except Exception:
        pass
