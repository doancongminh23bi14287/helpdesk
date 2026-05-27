# backend/app/services/email_piping.py
import imaplib
import email as email_lib
from email.header import decode_header
import re
from sqlalchemy.orm import Session
from app.models.ticket import Ticket, TicketReply
from app.models.notification import EmailLog
from app.models.user import User
from app.models.organization import Organization
from app import config


def _decode_str(value: str | None) -> str:
    """Decode RFC2047-encoded email header string."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(chunk)
    return "".join(decoded).strip()


def _get_text_body(msg) -> str:
    """Extract plain-text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


TICKET_REF_PATTERN = re.compile(r"\[#(\d+)\]")


def process_inbox(db: Session) -> int:
    """
    Connect to IMAP, fetch UNSEEN emails, process each one.
    Returns count of emails processed (not skipped).
    Each email is wrapped in try/except so one bad email never stops the batch.
    """
    processed = 0
    try:
        mail = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        mail.login(config.IMAP_USER, config.IMAP_PASS)
        mail.select("INBOX")
    except Exception as exc:
        # Log connection failure and return — don't crash the worker
        _log(db, None, None, None, None, "error", f"IMAP connect failed: {exc}")
        db.commit()
        return 0

    try:
        _, data = mail.search(None, "UNSEEN")
        uid_list = data[0].split() if data[0] else []
        for uid in uid_list:
            message_id = None
            from_email = None
            subject = None
            try:
                _, msg_data = mail.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw)

                message_id = msg.get("Message-ID", "").strip()
                from_email = email_lib.utils.parseaddr(msg.get("From", ""))[1].lower()
                subject = _decode_str(msg.get("Subject", "(no subject)"))[:300]
                body = _get_text_body(msg)

                # Dedup by Message-ID
                if message_id and db.query(EmailLog).filter(EmailLog.message_id == message_id).first():
                    _log(db, None, from_email, subject, None, "skipped", "duplicate message_id")
                    db.commit()
                    mail.store(uid, "+FLAGS", "\\Seen")
                    continue

                # Resolve sender -> user -> org
                sender_user = db.query(User).filter(User.email == from_email, User.is_active == True).first()
                if sender_user:
                    org_id = sender_user.org_id
                    raised_by = sender_user.id
                    raised_by_email = None
                else:
                    # Unknown sender — use PROVIDER org
                    provider = db.query(Organization).filter(Organization.code == "PROVIDER").first()
                    if not provider:
                        _log(db, message_id, from_email, subject, None, "error",
                             "Unknown sender and PROVIDER org not found")
                        db.commit()
                        mail.store(uid, "+FLAGS", "\\Seen")
                        continue
                    org_id = provider.id
                    raised_by = None
                    raised_by_email = from_email

                # Check if subject references existing ticket e.g. "[#42]"
                match = TICKET_REF_PATTERN.search(subject)
                if match:
                    ref_id = int(match.group(1))
                    existing = db.query(Ticket).filter(Ticket.id == ref_id, Ticket.is_deleted == False).first()
                    if existing:
                        reply = TicketReply(
                            ticket_id=ref_id,
                            author_id=raised_by,
                            author_email=raised_by_email or from_email,
                            content=body or subject,
                            is_internal=False,
                            source="email",
                        )
                        db.add(reply)
                        db.flush()
                        _log(db, message_id, from_email, subject, ref_id, "appended", None)
                        db.commit()
                        mail.store(uid, "+FLAGS", "\\Seen")
                        processed += 1
                        continue
                    else:
                        _log(db, message_id, from_email, subject, None, "error",
                             f"Referenced ticket #{ref_id} not found")
                        db.commit()
                        mail.store(uid, "+FLAGS", "\\Seen")
                        continue

                # Create new ticket
                ticket = Ticket(
                    org_id=org_id,
                    subject=subject,
                    description=body,
                    status="Open",
                    source="email",
                    raised_by=raised_by,
                    raised_by_email=raised_by_email or from_email,
                )
                db.add(ticket)
                db.flush()
                _log(db, message_id, from_email, subject, ticket.id, "created", None)
                db.commit()
                mail.store(uid, "+FLAGS", "\\Seen")
                processed += 1

            except Exception as exc:
                db.rollback()
                _log(db, message_id, from_email, subject, None, "error", f"Error processing email: {exc}")
                db.commit()
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return processed


def _log(db: Session, message_id, from_email, subject, ticket_id, action, detail):
    log = EmailLog(
        message_id=message_id,
        from_email=from_email,
        subject=subject,
        ticket_id=ticket_id,
        action=action,
        detail=detail,
    )
    db.add(log)
