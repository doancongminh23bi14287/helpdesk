"""Database-backed Gmail access-token refresh."""
from datetime import datetime, timedelta, timezone

from app.core.token_crypto import decrypt_secret, encrypt_secret
from app.models.email_oauth_credential import EmailOAuthCredential


def latest_credential(db):
    if db is None:
        return None
    return db.query(EmailOAuthCredential).order_by(EmailOAuthCredential.id.desc()).first()


def get_valid_access_token(db, credential, client_id: str, client_secret: str, post_json) -> str:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if credential.access_token and credential.token_expiry and credential.token_expiry > now + timedelta(minutes=2):
        return decrypt_secret(credential.access_token) or credential.access_token

    token = post_json(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": decrypt_secret(credential.refresh_token),
            "grant_type": "refresh_token",
        },
    )
    expires_in = max(60, int(token.get("expires_in", 3600)) - 60)
    credential.access_token = encrypt_secret(token["access_token"])
    credential.token_expiry = now + timedelta(seconds=expires_in)
    credential.status = "connected"
    db.commit()
    return token["access_token"]
