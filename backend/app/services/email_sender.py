"""Outbound email sender with SMTP/SSL and DB logging."""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from sqlalchemy.orm import Session
from app import config
from app.models.notification import EmailLog

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body_html: str, body_text: str = None, db: Session = None) -> bool:
    """
    Send an email via SMTP SSL. Returns True on success, False on failure.
    Logs result to email_log table if db is provided.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_USER))
        msg["To"] = to

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        if config.SMTP_USE_SSL:
            smtp_cls = smtplib.SMTP_SSL
        else:
            smtp_cls = smtplib.SMTP

        with smtp_cls(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            if not config.SMTP_USE_SSL:
                server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.sendmail(config.SMTP_USER, [to], msg.as_string())

        _log(db, to, subject, None, "outbound", "sent")
        return True

    except Exception as exc:
        logger.warning("Email send failed to %s: %s", to, exc)
        _log(db, to, subject, None, "outbound", f"failed: {exc}"[:255])
        return False


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


def notify_new_ticket(ticket, org_name: str, service_name: str, db: Session = None):
    """Send new ticket notification to admin."""
    subject = f"[#{ticket.id}] {ticket.subject}"
    ticket_url = f"http://localhost:5173/tickets/{ticket.id}"
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333">
<h2 style="color:#1a56db">New Support Ticket #{ticket.id}</h2>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:8px;font-weight:bold;width:140px">Subject</td><td style="padding:8px">{ticket.subject}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold">Organization</td><td style="padding:8px">{org_name or 'N/A'}</td></tr>
  <tr><td style="padding:8px;font-weight:bold">Service</td><td style="padding:8px">{service_name or 'N/A'}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:8px;font-weight:bold">Priority</td><td style="padding:8px">{ticket.priority}</td></tr>
  <tr><td style="padding:8px;font-weight:bold">Raised by</td><td style="padding:8px">{ticket.raised_by_email or 'N/A'}</td></tr>
</table>
<p style="margin-top:16px">
  <a href="{ticket_url}" style="background:#1a56db;color:white;padding:8px 16px;text-decoration:none;border-radius:4px">View Ticket</a>
</p>
<p style="color:#6b7280;font-size:12px;margin-top:24px">OSD Support System</p>
</body></html>"""
    body_text = f"New ticket #{ticket.id}: {ticket.subject}\nOrg: {org_name}\nPriority: {ticket.priority}\nLink: {ticket_url}"
    send_email(config.ADMIN_NOTIFICATION_EMAIL, subject, body_html, body_text, db=db)


def notify_ticket_reply(ticket, reply_content: str, sender_role: str, to_email: str, db: Session = None):
    """Send reply notification to the other party."""
    if not to_email:
        return
    subject = f"Re: [#{ticket.id}] {ticket.subject}"
    ticket_url = f"http://localhost:5173/tickets/{ticket.id}"
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
    send_email(to_email, subject, body_html, body_text, db=db)


def notify_status_changed(ticket, new_status: str, to_email: str, db: Session = None):
    """Send status change notification (Resolved / Closed only)."""
    if not to_email:
        return
    subject = f"[#{ticket.id}] Status changed to {new_status}"
    ticket_url = f"http://localhost:5173/tickets/{ticket.id}"
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
    send_email(to_email, subject, body_html, body_text, db=db)
