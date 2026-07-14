# backend/app/services/email_piping.py
import imaplib
import email as email_lib
from email.header import decode_header
import logging
import re
from sqlalchemy.orm import Session
from app.models.ticket import Ticket, TicketReply
from app.models.attachment import TicketAttachment
from app.models.notification import EmailLog
from app.models.email_thread import EmailThread
from app.models.user import User
from app.models.organization import Organization
from app.services.file_storage import save_attachment
from app import config

logger = logging.getLogger(__name__)


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

_ALLOWED_ATTACHMENT_PREFIXES = (
    "image/",
    "text/",
    "application/pdf",
    "application/zip",
    "application/x-zip",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument",
)
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


def _save_email_attachments(msg, ticket_id: int, org_id: int, db: Session) -> None:
    """Extract and persist email attachments to ticket_id. Skips invalid parts, never raises."""
    for part in msg.walk():
        disposition = part.get("Content-Disposition", "") or ""
        if "attachment" not in disposition.lower() and "inline" not in disposition.lower():
            continue
        filename = part.get_filename()
        if not filename:
            continue
        filename = _decode_str(filename)
        mime_type = part.get_content_type() or "application/octet-stream"
        if not any(mime_type.startswith(p) for p in _ALLOWED_ATTACHMENT_PREFIXES):
            logger.warning("Email attachment skipped — disallowed MIME %s (%s)", mime_type, filename)
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception as exc:
            logger.warning("Email attachment decode failed (%s): %s", filename, exc)
            continue
        if not payload:
            continue
        if len(payload) > _MAX_ATTACHMENT_BYTES:
            logger.warning("Email attachment too large, skipped (%s, %d bytes)", filename, len(payload))
            continue
        try:
            result = save_attachment(
                file_data=payload,
                org_id=org_id,
                original_filename=filename,
                mime_type=mime_type,
            )
        except Exception as exc:
            logger.warning("Email attachment save failed (%s): %s", filename, exc)
            continue
        attachment = TicketAttachment(
            ticket_id=ticket_id,
            file_name=filename,
            file_path=result["stored_path"],
            file_size=result["file_size"],
            mime_type=mime_type,
            detected_mime=result.get("detected_mime"),
            sha256=result.get("sha256"),
            uploaded_by=None,
        )
        db.add(attachment)
BOUNCE_SUBJECT_PATTERNS = (
    "failed to deliver",
    "undelivered mail returned to sender",
    "delivery status notification",
    "mail delivery subsystem",
    "failure notice",
    "returned mail",
)
BOUNCE_SENDERS = {
    "",
    "mailer-daemon",
    "postmaster",
}


def _is_delivery_status_notification(msg, from_email: str, subject: str) -> bool:
    """Detect SMTP bounce/DSN messages so they do not create customer tickets."""
    auto_submitted = (msg.get("Auto-Submitted") or "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return True

    content_type = msg.get_content_type().lower()
    if content_type in {"message/delivery-status", "multipart/report"}:
        report_type = (msg.get_param("report-type") or "").lower()
        if content_type == "message/delivery-status" or report_type == "delivery-status":
            return True

    return_path = (msg.get("Return-Path") or "").strip()
    if return_path == "<>":
        return True

    local_part = from_email.split("@", 1)[0].lower()
    if local_part in BOUNCE_SENDERS:
        return True

    normalized_subject = subject.lower()
    return any(pattern in normalized_subject for pattern in BOUNCE_SUBJECT_PATTERNS)


def _resolve_ticket_id(msg, subject: str, db: Session) -> int | None:
    """
    3-priority lookup to find an existing ticket for an inbound email.

    Priority 1: In-Reply-To header matches a known message_id in email_threads.
    Priority 2: References header — walk reversed list until a match is found.
    Priority 3: Subject [#N] pattern fallback.
    Returns ticket_id or None (caller treats None as "create new ticket").
    """
    # Priority 1 — In-Reply-To
    in_reply_to = msg.get("In-Reply-To", "").strip()
    if in_reply_to:
        thread = db.query(EmailThread).filter(
            EmailThread.message_id == in_reply_to
        ).first()
        if thread:
            return thread.ticket_id

    # Priority 2 — References (space-separated chain; most recent last)
    references = msg.get("References", "").strip()
    if references:
        for ref_id in reversed(references.split()):
            thread = db.query(EmailThread).filter(
                EmailThread.message_id == ref_id.strip()
            ).first()
            if thread:
                return thread.ticket_id

    # Priority 3 — Subject pattern [#N]
    match = TICKET_REF_PATTERN.search(subject)
    if match:
        return int(match.group(1))

    return None


def _sender_can_reply_to_ticket(
    ticket: Ticket,
    sender_user: User | None,
    from_email: str,
    db: Session,
) -> bool:
    """Authorize an inbound sender before appending to an existing ticket.

    Threading headers and subject references are routing hints, not proof of
    authorization. Customers may only reply to tickets they raised. Internal
    users must be active and have access to the ticket's organization.
    """
    normalized_email = (from_email or "").strip().lower()

    if sender_user:
        if not sender_user.is_active:
            return False
        if sender_user.role == "admin":
            return True
        if sender_user.role == "staff":
            from app.models.team import StaffOrgAssignment

            return db.query(StaffOrgAssignment).filter(
                StaffOrgAssignment.user_id == sender_user.id,
                StaffOrgAssignment.org_id == ticket.org_id,
            ).first() is not None
        return sender_user.id == ticket.raised_by and sender_user.org_id == ticket.org_id

    return bool(
        normalized_email
        and ticket.raised_by_email
        and normalized_email == ticket.raised_by_email.strip().lower()
    )


def _record_inbound_thread(
    db: Session,
    ticket_id: int,
    message_id: str | None,
    in_reply_to: str | None,
    references: str | None,
) -> None:
    thread = EmailThread(
        ticket_id=ticket_id,
        message_id=message_id or None,
        in_reply_to=in_reply_to or None,
        references=references or None,
        direction="inbound",
    )
    db.add(thread)


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
                if message_id and db.query(EmailLog).filter(
                    EmailLog.message_id == message_id
                ).first():
                    _log(db, None, from_email, subject, None, "skipped", "duplicate message_id")
                    db.commit()
                    mail.store(uid, "+FLAGS", "\\Seen")
                    continue

                if _is_delivery_status_notification(msg, from_email, subject):
                    _log(db, message_id, from_email, subject, None, "skipped",
                         "delivery status notification ignored")
                    db.commit()
                    mail.store(uid, "+FLAGS", "\\Seen")
                    continue

                # Resolve sender -> user -> org
                sender_user = db.query(User).filter(
                    User.email == from_email, User.is_active == True
                ).first()
                if sender_user:
                    org_id = sender_user.org_id
                    raised_by = sender_user.id
                    raised_by_email = None
                else:
                    provider = db.query(Organization).filter(
                        Organization.code == "PROVIDER"
                    ).first()
                    if not provider:
                        _log(db, message_id, from_email, subject, None, "error",
                             "Unknown sender and PROVIDER org not found")
                        db.commit()
                        mail.store(uid, "+FLAGS", "\\Seen")
                        continue
                    org_id = provider.id
                    raised_by = None
                    raised_by_email = from_email

                in_reply_to_hdr = msg.get("In-Reply-To", "").strip() or None
                references_hdr = msg.get("References", "").strip() or None

                # Resolve ticket via 3-priority strategy
                ticket_id = _resolve_ticket_id(msg, subject, db)
                rerouted_reason = None

                if ticket_id is not None:
                    existing = db.query(Ticket).filter(
                        Ticket.id == ticket_id, Ticket.is_deleted == False
                    ).first()
                    if existing and _sender_can_reply_to_ticket(
                        existing, sender_user, from_email, db
                    ):
                        reply = TicketReply(
                            ticket_id=ticket_id,
                            author_id=raised_by,
                            author_email=raised_by_email or from_email,
                            content=body or subject,
                            is_internal=False,
                            source="email",
                        )
                        db.add(reply)
                        db.flush()
                        _save_email_attachments(msg, ticket_id, org_id, db)
                        _record_inbound_thread(
                            db, ticket_id, message_id, in_reply_to_hdr, references_hdr
                        )
                        _log(db, message_id, from_email, subject, ticket_id, "appended", None)
                        db.commit()
                        mail.store(uid, "+FLAGS", "\\Seen")
                        processed += 1
                        continue
                    elif existing:
                        rerouted_reason = "sender not authorized for referenced ticket"
                        ticket_id = None
                    else:
                        _log(db, message_id, from_email, subject, None, "error",
                             f"Referenced ticket #{ticket_id} not found")
                        db.commit()
                        mail.store(uid, "+FLAGS", "\\Seen")
                        continue

                # No existing ticket found — create new
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
                _save_email_attachments(msg, ticket.id, org_id, db)
                _record_inbound_thread(
                    db, ticket.id, message_id, in_reply_to_hdr, references_hdr
                )
                _log(
                    db,
                    message_id,
                    from_email,
                    subject,
                    ticket.id,
                    "created",
                    rerouted_reason,
                )
                db.commit()
                mail.store(uid, "+FLAGS", "\\Seen")
                processed += 1

            except Exception as exc:
                db.rollback()
                _log(db, message_id, from_email, subject, None, "error",
                     f"Error processing email: {exc}")
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
        detail=str(detail)[:255] if detail is not None else None,
    )
    db.add(log)
