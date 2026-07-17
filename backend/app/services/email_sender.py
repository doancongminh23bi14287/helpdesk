"""Outbound email sender via Gmail API (fallback: SMTP) with DB logging."""
import html
import logging
import os
import time
import uuid
from sqlalchemy.orm import Session
from app import config
from app.models.notification import EmailLog

logger = logging.getLogger(__name__)

_GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
_GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
_GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")
_GMAIL_ACCESS_TOKEN = ""
_GMAIL_ACCESS_TOKEN_EXPIRES_AT = 0.0


def _sanitize_header_value(value: str | None, field: str) -> str:
    text = (value or "").strip()
    if "\r" in text or "\n" in text:
        raise ValueError(f"Invalid characters in email {field}")
    return text


def send_email(
    to: str,
    subject: str,
    body_html: str,
    body_text: str = None,
    db: Session = None,
    ticket_id: int = None,
) -> str | None:
    """
    Send an email via Gmail API (or SMTP if OAuth env vars are not set).
    Returns a unique Message-ID on success, None on failure.
    Logs result to email_log table if db is provided.
    """
    log_subject = (subject or "").replace("\r", " ").replace("\n", " ")
    log_to = (to or "").replace("\r", " ").replace("\n", " ")
    try:
        subject = _sanitize_header_value(subject, "subject")
        to = _sanitize_header_value(to, "recipient")
        # Message-ID domain must match the sending address for DMARC alignment
        sender_domain = config.SMTP_FROM_EMAIL.rsplit("@", 1)[-1] or "localhost"
        outbound_message_id = f"<{uuid.uuid4()}@{sender_domain}>"
        if _GMAIL_CLIENT_ID and _GMAIL_REFRESH_TOKEN:
            _send_via_gmail(to, subject, body_html, body_text, outbound_message_id)
        else:
            _send_via_smtp(to, subject, body_html, body_text, outbound_message_id)

        _log(db, log_to, log_subject, ticket_id, "outbound", "sent")
        return outbound_message_id

    except Exception as exc:
        logger.warning("Email send failed to %r: %s", log_to, exc)
        _log(db, log_to, log_subject, ticket_id, "outbound", f"failed: {exc}"[:255])
        return None


def _send_via_gmail(to, subject, body_html, body_text, message_id):
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr

    access_token = _get_gmail_access_token()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _sanitize_header_value(subject, "subject")
    msg["From"] = formataddr((_sanitize_header_value(config.SMTP_FROM_NAME, "from name"), _sanitize_header_value(config.SMTP_FROM_EMAIL, "from address")))
    msg["To"] = _sanitize_header_value(to, "recipient")
    msg["Message-ID"] = message_id
    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = _post_google_json(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        json={"raw": raw},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    logger.info("Email sent via Gmail API to %s (id=%s)", to, result.get("id"))


def _get_gmail_access_token() -> str:
    """Return a cached Gmail access token, refreshing it only when needed."""
    global _GMAIL_ACCESS_TOKEN, _GMAIL_ACCESS_TOKEN_EXPIRES_AT
    if _GMAIL_ACCESS_TOKEN and time.monotonic() < _GMAIL_ACCESS_TOKEN_EXPIRES_AT:
        return _GMAIL_ACCESS_TOKEN

    token = _post_google_json("https://oauth2.googleapis.com/token", data={
        "client_id": _GMAIL_CLIENT_ID,
        "client_secret": _GMAIL_CLIENT_SECRET,
        "refresh_token": _GMAIL_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    _GMAIL_ACCESS_TOKEN = token["access_token"]
    expires_in = max(60, int(token.get("expires_in", 3600)) - 60)
    _GMAIL_ACCESS_TOKEN_EXPIRES_AT = time.monotonic() + expires_in
    return _GMAIL_ACCESS_TOKEN


def _post_google_json(url: str, **kwargs) -> dict:
    """POST to Google with short retries for transient connection resets."""
    import httpx

    last_error = None
    for attempt in range(3):
        try:
            response = httpx.post(url, timeout=20, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.TransportError as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))
    raise last_error


def _send_via_smtp(to, subject, body_html, body_text, message_id):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _sanitize_header_value(subject, "subject")
    msg["From"] = formataddr((_sanitize_header_value(config.SMTP_FROM_NAME, "from name"), _sanitize_header_value(config.SMTP_FROM_EMAIL, "from address")))
    msg["To"] = _sanitize_header_value(to, "recipient")
    msg["Message-ID"] = message_id

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    smtp_cls = smtplib.SMTP_SSL if config.SMTP_USE_SSL else smtplib.SMTP
    with smtp_cls(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
        if not config.SMTP_USE_SSL:
            server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASS)
        server.sendmail(config.SMTP_FROM_EMAIL, [to], msg.as_string())


def _record_outbound_thread(db: Session, ticket_id: int, message_id: str) -> None:
    """Insert an outbound EmailThread row so future replies can reference it."""
    if db is None or not ticket_id or not message_id:
        return
    from app.models.email_thread import EmailThread
    try:
        thread = EmailThread(
            ticket_id=ticket_id,
            message_id=message_id,
            direction="outbound",
        )
        db.add(thread)
        db.commit()
    except Exception as exc:
        logger.warning("EmailThread record failed: %s", exc)
        db.rollback()


def _log(db: Session, to: str, subject: str, ticket_id, action: str, detail: str):
    if db is None:
        return
    try:
        log = EmailLog(
            from_email=to,   # reuse from_email to store recipient
            subject=subject[:300] if subject else None,
            ticket_id=ticket_id,
            action=action,
            detail=detail[:255] if detail else None,
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        logger.warning("Email log failed: %s", exc)
        db.rollback()


def _fmt_vn_time(dt) -> str:
    """Format a UTC-naive datetime as dd/mm/yyyy HH:MM in Vietnam time (UTC+7)."""
    if not dt:
        return "N/A"
    from datetime import timedelta
    return (dt + timedelta(hours=7)).strftime("%d/%m/%Y %H:%M")


def _excerpt(text: str, limit: int = 300) -> str:
    """HTML-escaped excerpt of user-supplied text, truncated with ellipsis."""
    if not text:
        return ""
    text = text.strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return html.escape(text)


def _creator_full_name(ticket, db: Session) -> str | None:
    """Look up the full name of the user who raised the ticket."""
    if db is None or not getattr(ticket, "raised_by", None):
        return None
    from app.models.user import User
    user = db.query(User).filter(User.id == ticket.raised_by).first()
    return user.full_name if user and user.full_name else None


def notify_new_ticket(ticket, org_name: str, service_name: str, db: Session = None) -> None:
    """Send new ticket notification to admin AND confirmation to creator."""
    ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket.id}"
    subject_esc = html.escape(ticket.subject or "")
    org_esc = html.escape(org_name) if org_name else "N/A"
    service_esc = html.escape(service_name) if service_name else "N/A"
    desc_excerpt = _excerpt(getattr(ticket, "description", None))
    created_str = _fmt_vn_time(getattr(ticket, "created_at", None))

    excerpt_block_html = (
        f'<div style="background:#f9fafb;padding:12px;border-left:3px solid #1a56db;'
        f'margin:16px 0;color:#374151;font-size:14px">{desc_excerpt}</div>'
        if desc_excerpt else ""
    )

    # — Admin notification —
    admin_subject = f"[Ticket #{ticket.id}] {ticket.subject}"
    admin_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">
<h2 style="color:#1a56db">New Support Ticket #{ticket.id}</h2>
<table style="border-collapse:collapse;width:100%;margin-bottom:16px">
  <tr><td style="padding:8px;font-weight:bold;width:140px;border-bottom:1px solid #e5e7eb">Subject</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{subject_esc}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Organization</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{org_esc}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Service</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{service_esc}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Priority</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{html.escape(str(ticket.priority or 'N/A'))}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Raised by</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{html.escape(ticket.raised_by_email or 'N/A')}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold">Created</td><td style="padding:8px">{created_str} (GMT+7)</td></tr>
</table>
{excerpt_block_html}
<a href="{ticket_url}" style="background:#1a56db;color:white;padding:10px 20px;text-decoration:none;border-radius:6px;display:inline-block">View &amp; Assign Ticket</a>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>
</body></html>"""
    admin_text = (
        f"New ticket #{ticket.id}: {ticket.subject}\nOrg: {org_name}\nService: {service_name}\n"
        f"Priority: {ticket.priority}\nRaised by: {ticket.raised_by_email}\nCreated: {created_str} (GMT+7)\n\n"
        f"{(ticket.description or '')[:300]}\n\nView: {ticket_url}"
    )
    send_email(config.ADMIN_NOTIFICATION_EMAIL, admin_subject, admin_html, admin_text, db=db)

    # — Creator confirmation (record thread so their reply can be threaded) —
    creator_email = ticket.raised_by_email
    if creator_email and creator_email != config.ADMIN_NOTIFICATION_EMAIL:
        full_name = _creator_full_name(ticket, db)
        greeting = f"Chào {html.escape(full_name)}," if full_name else "Chào Quý khách,"
        creator_subject = f"[Ticket #{ticket.id}] Yêu cầu hỗ trợ đã được tiếp nhận"
        creator_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">
<h2 style="color:#1a56db">Yêu cầu hỗ trợ #{ticket.id} đã được tiếp nhận</h2>
<p>{greeting}</p>
<p>Cảm ơn bạn đã liên hệ. Đội ngũ hỗ trợ của chúng tôi sẽ phản hồi sớm nhất có thể.</p>
<table style="border-collapse:collapse;width:100%;margin:16px 0">
  <tr><td style="padding:8px;font-weight:bold;width:140px;border-bottom:1px solid #e5e7eb">Tiêu đề</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{subject_esc}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Tổ chức</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{org_esc}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Dịch vụ</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{service_esc}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Mức độ</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{html.escape(str(ticket.priority or 'N/A'))}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Thời gian tạo</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{created_str} (GMT+7)</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold">Mã ticket</td><td style="padding:8px">#{ticket.id}</td></tr>
</table>
{f'<p style="margin-bottom:4px;color:#6b7280;font-size:13px">Nội dung bạn đã gửi:</p>{excerpt_block_html}' if desc_excerpt else ''}
<a href="{ticket_url}" style="background:#1a56db;color:white;padding:10px 20px;text-decoration:none;border-radius:6px;display:inline-block">Xem ticket của bạn</a>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System — Nếu bạn không tạo yêu cầu này, vui lòng bỏ qua email.</p>
</body></html>"""
        creator_text = (
            f"{greeting.rstrip(',')}\n\nYêu cầu hỗ trợ #{ticket.id} đã được tiếp nhận.\n"
            f"Tiêu đề: {ticket.subject}\nTổ chức: {org_name or 'N/A'}\nMức độ: {ticket.priority}\n"
            f"Thời gian tạo: {created_str} (GMT+7)\n\n"
            f"Nội dung: {(ticket.description or '')[:300]}\n\nXem tại: {ticket_url}"
        )
        mid = send_email(creator_email, creator_subject, creator_html, creator_text,
                         db=db, ticket_id=ticket.id)
        _record_outbound_thread(db, ticket.id, mid)


def bg_notify_new_ticket(ticket_id: int, org_name: str, service_name: str) -> None:
    """Background-task wrapper — creates its own DB session."""
    if not config.EMAIL_FEATURES_ENABLED:
        return
    from app.database import SessionLocal
    from app.models.ticket import Ticket
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            notify_new_ticket(ticket, org_name=org_name, service_name=service_name, db=db)
    finally:
        db.close()


def bg_send_email(to: str, subject: str, body_html: str, body_text: str = None) -> None:
    """Background-task wrapper for a one-off email."""
    send_email(to, subject, body_html, body_text)


def notify_ticket_reply(ticket, reply_content: str, sender_role: str, to_email: str,
                        db: Session = None, recipient_name: str = None) -> None:
    """Send reply notification to the other party."""
    if not to_email:
        return
    subject = f"Re: [#{ticket.id}] {ticket.subject}"
    ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket.id}"
    greeting = f"Chào {html.escape(recipient_name)}," if recipient_name else "Chào Quý khách,"
    reply_esc = _excerpt(reply_content, 500)
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">
<h2 style="color:#1a56db">Phản hồi mới trên ticket #{ticket.id}</h2>
<p>{greeting}</p>
<p>Ticket <strong>{html.escape(ticket.subject or '')}</strong> vừa có phản hồi mới:</p>
<div style="background:#f9fafb;padding:12px;border-left:3px solid #1a56db;margin:16px 0">
  {reply_esc}
</div>
<p>
  <a href="{ticket_url}" style="background:#1a56db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px">Xem ticket</a>
</p>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>
</body></html>"""
    body_text = (
        f"{greeting.rstrip(',')}\n\nPhản hồi mới trên ticket #{ticket.id}: {ticket.subject}\n\n"
        f"{(reply_content or '')[:200]}\n\nXem tại: {ticket_url}"
    )
    mid = send_email(to_email, subject, body_html, body_text, db=db, ticket_id=ticket.id)
    _record_outbound_thread(db, ticket.id, mid)


def notify_status_changed(ticket, new_status: str, to_email: str,
                          db: Session = None, recipient_name: str = None) -> None:
    """Send status change notification (Resolved / Closed only)."""
    if not to_email:
        return
    subject = f"[#{ticket.id}] Status changed to {new_status}"
    ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket.id}"
    greeting = f"Chào {html.escape(recipient_name)}," if recipient_name else "Chào Quý khách,"
    status_esc = html.escape(str(new_status))
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">
<h2 style="color:#1a56db">Ticket #{ticket.id} — {status_esc}</h2>
<p>{greeting}</p>
<p>Ticket <strong>{html.escape(ticket.subject or '')}</strong> của bạn đã được cập nhật trạng thái: <strong>{status_esc}</strong></p>
<p>
  <a href="{ticket_url}" style="background:#1a56db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px">Xem ticket</a>
</p>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>
</body></html>"""
    body_text = (
        f"{greeting.rstrip(',')}\n\nTicket #{ticket.id} '{ticket.subject}' đã chuyển sang trạng thái {new_status}.\n"
        f"Xem tại: {ticket_url}"
    )
    mid = send_email(to_email, subject, body_html, body_text, db=db, ticket_id=ticket.id)
    _record_outbound_thread(db, ticket.id, mid)
