"""Persistence step for the Gmail OAuth browser callback."""
from fastapi.responses import RedirectResponse

from app import config
from app.core.token_crypto import encrypt_secret
from app.models.email_oauth_credential import EmailOAuthCredential
from app.services import email_oauth


def complete_email_oauth(code: str, callback_user, db):
    frontend = f"{config.FRONTEND_URL}/admin/email-outbox"
    if callback_user.role != "admin":
        return RedirectResponse(url=f"{frontend}?gmail_error=invalid_state")
    try:
        tokens = email_oauth.exchange_code(code)
    except Exception:
        return RedirectResponse(url=f"{frontend}?gmail_error=token_exchange_failed")

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    if not refresh_token or not access_token:
        return RedirectResponse(url=f"{frontend}?gmail_error=invalid_token_response")

    credential = db.query(EmailOAuthCredential).order_by(EmailOAuthCredential.id.desc()).first()
    if credential is None:
        credential = EmailOAuthCredential()
        db.add(credential)
    credential.refresh_token = encrypt_secret(refresh_token)
    credential.access_token = encrypt_secret(access_token)
    credential.token_expiry = email_oauth.token_expiry(tokens)
    credential.connected_by = callback_user.id
    credential.status = "connected"
    try:
        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse(url=f"{frontend}?gmail_error=connection_failed")
    return RedirectResponse(url=f"{frontend}?gmail_connected=1")
