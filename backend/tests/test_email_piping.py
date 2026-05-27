# backend/tests/test_email_piping.py
import pytest
from unittest.mock import patch, MagicMock
import email as email_lib
import email.mime.text


def _make_email_bytes(from_addr: str, subject: str, body: str, message_id: str = None) -> bytes:
    """Build a minimal RFC822 email bytes object."""
    msg = email_lib.mime.text.MIMEText(body, "plain", "utf-8")
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg["To"] = "ticket@osd.vn"
    if message_id:
        msg["Message-ID"] = message_id
    return msg.as_bytes()


def _mock_imap(emails: list[tuple[str, str, str, str]]):
    """
    Return a context-manager-compatible mock IMAP4_SSL.
    emails: list of (from_addr, subject, body, message_id)
    """
    mock_mail = MagicMock()
    mock_mail.login.return_value = ("OK", [])
    mock_mail.select.return_value = ("OK", [b"1"])

    uid_list = " ".join(str(i + 1) for i in range(len(emails))).encode()
    mock_mail.search.return_value = ("OK", [uid_list])

    fetch_responses = []
    for from_addr, subject, body, mid in emails:
        raw = _make_email_bytes(from_addr, subject, body, mid)
        fetch_responses.append(("OK", [(b"1 (RFC822 {N})", raw)]))
    mock_mail.fetch.side_effect = fetch_responses
    mock_mail.store.return_value = ("OK", [])
    mock_mail.logout.return_value = ("BYE", [])
    return mock_mail


def test_email_creates_ticket_with_status_open(db, client_org, customer_user):
    """Email from known sender creates ticket with status=Open."""
    from app.services.email_piping import process_inbox

    mock_mail = _mock_imap([
        (customer_user.email, "Need help", "Please assist me", "<msg1@test>"),
    ])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1
    from app.models.ticket import Ticket
    ticket = db.query(Ticket).filter(Ticket.source == "email").first()
    assert ticket is not None
    assert ticket.status == "Open"
    assert ticket.raised_by == customer_user.id
    assert ticket.org_id == customer_user.org_id


def test_email_dedup_by_message_id(db, customer_user):
    """Same Message-ID processed twice → only one ticket created."""
    from app.services.email_piping import process_inbox

    mock_mail = _mock_imap([
        (customer_user.email, "Dup test", "Body", "<dup-msg@test>"),
    ])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count1 = process_inbox(db)

    # Second run with same message_id
    mock_mail2 = _mock_imap([
        (customer_user.email, "Dup test", "Body", "<dup-msg@test>"),
    ])
    with patch("imaplib.IMAP4_SSL", return_value=mock_mail2):
        count2 = process_inbox(db)

    assert count1 == 1
    assert count2 == 0  # deduped — skipped
    from app.models.ticket import Ticket
    tickets = db.query(Ticket).filter(Ticket.source == "email").all()
    assert len(tickets) == 1
    from app.models.notification import EmailLog
    skipped_log = db.query(EmailLog).filter(
        EmailLog.action == "skipped",
        EmailLog.detail == "duplicate message_id",
    ).first()
    assert skipped_log is not None


def test_email_unknown_sender_uses_provider_org(db):
    """Unknown sender email creates ticket under PROVIDER org."""
    from app.models.organization import Organization
    from app.services.email_piping import process_inbox

    provider = Organization(name="OSD Provider", code="PROVIDER", status="active")
    db.add(provider)
    db.commit()
    db.refresh(provider)

    mock_mail = _mock_imap([
        ("unknown@external.com", "Mystery issue", "Help!", "<unknown@test>"),
    ])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1
    from app.models.ticket import Ticket
    ticket = db.query(Ticket).filter(Ticket.source == "email").first()
    assert ticket is not None
    assert ticket.raised_by is None
    assert ticket.raised_by_email == "unknown@external.com"
    assert ticket.org_id == provider.id


def test_email_subject_with_ticket_ref_appends_reply(db, client_org, customer_user, service):
    """Subject containing [#N] appends reply to existing ticket instead of creating new one."""
    from app.models.ticket import Ticket
    from app.services.email_piping import process_inbox

    # Create existing ticket
    ticket = Ticket(
        org_id=client_org.id, service_id=service.id,
        subject="Original", status="Open", raised_by=customer_user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    mock_mail = _mock_imap([
        (customer_user.email, f"Re: [#{ticket.id}] Original", "Follow-up", "<reply@test>"),
    ])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1
    from app.models.ticket import TicketReply
    replies = db.query(TicketReply).filter(TicketReply.ticket_id == ticket.id).all()
    assert len(replies) == 1
    assert replies[0].source == "email"
    # No new ticket created — only the pre-existing one exists
    all_tickets = db.query(Ticket).all()
    assert len(all_tickets) == 1


def test_email_logged_to_email_log(db, customer_user):
    """Processed emails are logged to email_log table."""
    from app.services.email_piping import process_inbox
    from app.models.notification import EmailLog

    mock_mail = _mock_imap([
        (customer_user.email, "Log me", "Body text", "<logme@test>"),
    ])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        process_inbox(db)

    log = db.query(EmailLog).filter(EmailLog.message_id == "<logme@test>").first()
    assert log is not None
    assert log.action == "created"
    assert log.from_email == customer_user.email
