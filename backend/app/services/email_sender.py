"""Outbound email sender via Brevo API (fallback: SMTP) with DB logging."""
import logging
import os
import uuid
from sqlalchemy.orm import Session
from app import config
from app.models.notification import EmailLog

logger = logging.getLogger(__name__)

_BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")


def send_email(
    to: str,
    subject: str,
    body_html: str,
    body_text: str = None,
    db: Session = None,
    ticket_id: int = None,
) -> str | None:
    """
    Send an email via SendGrid HTTP API (or SMTP if no API key set).
    Returns a unique Message-ID on success, None on failure.
    Logs result to email_log table if db is provided.
    """
    outbound_message_id = f"<{uuid.uuid4()}@osd.vn>"
    try:
        if _BREVO_API_KEY:
            _send_via_brevo(to, subject, body_html, body_text, outbound_message_id)
        else:
            _send_via_smtp(to, subject, body_html, body_text, outbound_message_id)

        _log(db, to, subject, ticket_id, "outbound", "sent")
        return outbound_message_id

    except Exception as exc:
        logger.warning("Email send failed to %s: %s", to, exc)
        _log(db, to, subject, ticket_id, "outbound", f"failed: {exc}"[:255])
        return None


def _send_via_brevo(to, subject, body_html, body_text, message_id):
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = _BREVO_API_KEY

    api = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    sender = {"name": config.SMTP_FROM_NAME, "email": config.SMTP_FROM_EMAIL}
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to}],
        sender=sender,
        subject=subject,
        html_content=body_html,
        text_content=body_text,
        headers={"Message-ID": message_id},
    )
    result = api.send_transac_email(send_smtp_email)
    logger.info("Email sent via Brevo to %s (messageId=%s)", to, result.message_id)


def _send_via_smtp(to, subject, body_html, body_text, message_id):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_FROM_EMAIL))
    msg["To"] = to
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


def notify_new_ticket(ticket, org_name: str, service_name: str, db: Session = None) -> None:
    """Send new ticket notification to admin AND confirmation to creator."""
    ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket.id}"

    # — Admin notification —
    admin_subject = f"[Ticket #{ticket.id}] {ticket.subject}"
    admin_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">
<h2 style="color:#1a56db">New Support Ticket #{ticket.id}</h2>
<table style="border-collapse:collapse;width:100%;margin-bottom:16px">
  <tr><td style="padding:8px;font-weight:bold;width:140px;border-bottom:1px solid #e5e7eb">Subject</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{ticket.subject}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Organization</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{org_name or 'N/A'}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Service</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{service_name or 'N/A'}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Priority</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{ticket.priority}</td></tr>
  <tr><td style="padding:8px;font-weight:bold">Raised by</td><td style="padding:8px">{ticket.raised_by_email or 'N/A'}</td></tr>
</table>
<a href="{ticket_url}" style="background:#1a56db;color:white;padding:10px 20px;text-decoration:none;border-radius:6px;display:inline-block">View &amp; Assign Ticket</a>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>
</body></html>"""
    admin_text = f"New ticket #{ticket.id}: {ticket.subject}\nOrg: {org_name}\nService: {service_name}\nPriority: {ticket.priority}\nRaised by: {ticket.raised_by_email}\n\nView: {ticket_url}"
    send_email(config.ADMIN_NOTIFICATION_EMAIL, admin_subject, admin_html, admin_text, db=db)

    # — Creator confirmation (record thread so their reply can be threaded) —
    creator_email = ticket.raised_by_email
    if creator_email and creator_email != config.ADMIN_NOTIFICATION_EMAIL:
        creator_subject = f"[Ticket #{ticket.id}] Yêu cầu hỗ trợ đã được tiếp nhận"
        creator_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">
<h2 style="color:#1a56db">Yêu cầu hỗ trợ #{ticket.id} đã được tiếp nhận</h2>
<p>Cảm ơn bạn đã liên hệ. Đội ngũ hỗ trợ của chúng tôi sẽ phản hồi sớm nhất có thể.</p>
<table style="border-collapse:collapse;width:100%;margin:16px 0">
  <tr><td style="padding:8px;font-weight:bold;width:140px;border-bottom:1px solid #e5e7eb">Tiêu đề</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{ticket.subject}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Dịch vụ</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{service_name or 'N/A'}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #e5e7eb">Mức độ</td><td style="padding:8px;border-bottom:1px solid #e5e7eb">{ticket.priority}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold">Mã ticket</td><td style="padding:8px">#{ticket.id}</td></tr>
</table>
<a href="{ticket_url}" style="background:#1a56db;color:white;padding:10px 20px;text-decoration:none;border-radius:6px;display:inline-block">Xem ticket của bạn</a>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System — Nếu bạn không tạo yêu cầu này, vui lòng bỏ qua email.</p>
</body></html>"""
        creator_text = f"Yêu cầu hỗ trợ #{ticket.id} đã được tiếp nhận.\nTiêu đề: {ticket.subject}\nMức độ: {ticket.priority}\nXem tại: {ticket_url}"
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


def notify_ticket_reply(ticket, reply_content: str, sender_role: str, to_email: str, db: Session = None) -> None:
    """Send reply notification to the other party."""
    if not to_email:
        return
    subject = f"Re: [#{ticket.id}] {ticket.subject}"
    ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket.id}"
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333">
<h2 style="color:#1a56db">New Reply on Ticket #{ticket.id}</h2>
<p><strong>{ticket.subject}</strong></p>
<div style="background:#f9fafb;padding:12px;border-left:3px solid #1a56db;margin:16px 0">
  {reply_content[:500]}
</div>
<p>
  <a href="{ticket_url}" style="background:#1a56db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px">View Ticket</a>
</p>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>
</body></html>"""
    body_text = f"New reply on ticket #{ticket.id}: {ticket.subject}\n\n{reply_content[:200]}\n\nLink: {ticket_url}"
    mid = send_email(to_email, subject, body_html, body_text, db=db, ticket_id=ticket.id)
    _record_outbound_thread(db, ticket.id, mid)


def notify_status_changed(ticket, new_status: str, to_email: str, db: Session = None) -> None:
    """Send status change notification (Resolved / Closed only)."""
    if not to_email:
        return
    subject = f"[#{ticket.id}] Status changed to {new_status}"
    ticket_url = f"{config.FRONTEND_URL}/tickets/{ticket.id}"
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333">
<h2 style="color:#1a56db">Ticket #{ticket.id} — {new_status}</h2>
<p>Your ticket <strong>{ticket.subject}</strong> has been updated to status: <strong>{new_status}</strong></p>
<p>
  <a href="{ticket_url}" style="background:#1a56db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px">View Ticket</a>
</p>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>
</body></html>"""
    body_text = f"Ticket #{ticket.id} '{ticket.subject}' status changed to {new_status}.\nLink: {ticket_url}"
    mid = send_email(to_email, subject, body_html, body_text, db=db, ticket_id=ticket.id)
    _record_outbound_thread(db, ticket.id, mid)
