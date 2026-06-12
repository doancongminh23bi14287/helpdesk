# backend/tests/test_email_threading.py
"""
Tests for email threading via In-Reply-To / References / subject-pattern fallback.
Each test simulates an inbound email processed by process_inbox() and verifies
that the correct ticket resolution strategy was used.
"""
import pytest
from unittest.mock import patch, MagicMock
import email as email_lib
import email.mime.text


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_email_bytes(
    from_addr: str,
    subject: str,
    body: str,
    message_id: str = None,
    in_reply_to: str = None,
    references: str = None,
) -> bytes:
    msg = email_lib.mime.text.MIMEText(body, "plain", "utf-8")
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg["To"] = "ticket@osd.vn"
    if message_id:
        msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    return msg.as_bytes()


def _mock_imap(emails: list[tuple]) -> MagicMock:
    """
    emails: list of dicts with keys: from_addr, subject, body, message_id,
            in_reply_to (opt), references (opt).
    """
    mock_mail = MagicMock()
    mock_mail.login.return_value = ("OK", [])
    mock_mail.select.return_value = ("OK", [b"1"])

    uid_list = " ".join(str(i + 1) for i in range(len(emails))).encode()
    mock_mail.search.return_value = ("OK", [uid_list])

    fetch_responses = []
    for e in emails:
        raw = _make_email_bytes(
            e["from_addr"], e["subject"], e["body"],
            e.get("message_id"), e.get("in_reply_to"), e.get("references"),
        )
        fetch_responses.append(("OK", [(b"1 (RFC822 {N})", raw)]))

    mock_mail.fetch.side_effect = fetch_responses
    mock_mail.store.return_value = ("OK", [])
    mock_mail.logout.return_value = ("BYE", [])
    return mock_mail


def _seed_ticket(db, client_org, customer_user, service):
    from app.models.ticket import Ticket
    ticket = Ticket(
        org_id=client_org.id,
        service_id=service.id,
        subject="Original issue",
        status="Open",
        raised_by=customer_user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def _seed_thread(db, ticket_id: int, message_id: str, direction: str = "outbound"):
    from app.models.email_thread import EmailThread
    t = EmailThread(ticket_id=ticket_id, message_id=message_id, direction=direction)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ── tests ─────────────────────────────────────────────────────────────────────

def test_reply_matched_by_in_reply_to(db, client_org, customer_user, service):
    """
    Inbound email with In-Reply-To matching a known message_id is appended
    as a reply to the existing ticket — no new ticket is created.
    """
    from app.services.email_piping import process_inbox
    from app.models.ticket import Ticket, TicketReply

    ticket = _seed_ticket(db, client_org, customer_user, service)
    original_mid = "<original-staff-reply@osd.vn>"
    _seed_thread(db, ticket.id, original_mid, direction="outbound")

    mock_mail = _mock_imap([{
        "from_addr": customer_user.email,
        "subject": "Re: Original issue",  # no [#N] tag — relies purely on header
        "body": "Thanks, but still broken.",
        "message_id": "<customer-reply-1@mail.example>",
        "in_reply_to": original_mid,
    }])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1

    # Only the seeded ticket should exist — no new ticket
    all_tickets = db.query(Ticket).all()
    assert len(all_tickets) == 1

    # Reply was appended to correct ticket
    replies = db.query(TicketReply).filter(TicketReply.ticket_id == ticket.id).all()
    assert len(replies) == 1
    assert replies[0].source == "email"


def test_reply_matched_by_references(db, client_org, customer_user, service):
    """
    Inbound email with no In-Reply-To but References header pointing to a known
    message_id is still threaded onto the existing ticket.
    """
    from app.services.email_piping import process_inbox
    from app.models.ticket import Ticket, TicketReply

    ticket = _seed_ticket(db, client_org, customer_user, service)
    root_mid = "<root-message@osd.vn>"
    _seed_thread(db, ticket.id, root_mid, direction="outbound")

    # References chain: root → intermediate → current (last is most recent)
    references_chain = f"{root_mid} <intermediate@mail.example>"

    mock_mail = _mock_imap([{
        "from_addr": customer_user.email,
        "subject": "Still having issues",
        "body": "Problem persists.",
        "message_id": "<customer-ref-reply@mail.example>",
        # no In-Reply-To; only References
        "references": references_chain,
    }])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1

    all_tickets = db.query(Ticket).all()
    assert len(all_tickets) == 1

    replies = db.query(TicketReply).filter(TicketReply.ticket_id == ticket.id).all()
    assert len(replies) == 1


def test_reply_fallback_to_subject_pattern(db, client_org, customer_user, service):
    """
    Email with no threading headers but [#N] in subject is matched via
    the subject-pattern fallback and appended as a reply.
    """
    from app.services.email_piping import process_inbox
    from app.models.ticket import Ticket, TicketReply

    ticket = _seed_ticket(db, client_org, customer_user, service)

    mock_mail = _mock_imap([{
        "from_addr": customer_user.email,
        "subject": f"Re: [#{ticket.id}] Original issue",
        "body": "Following up.",
        "message_id": "<subj-fallback@mail.example>",
    }])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1

    all_tickets = db.query(Ticket).all()
    assert len(all_tickets) == 1

    replies = db.query(TicketReply).filter(TicketReply.ticket_id == ticket.id).all()
    assert len(replies) == 1


def test_reply_no_match_creates_new_ticket(db, client_org, customer_user, service):
    """
    Email with no headers and no subject pattern creates a brand-new ticket.
    """
    from app.services.email_piping import process_inbox
    from app.models.ticket import Ticket

    mock_mail = _mock_imap([{
        "from_addr": customer_user.email,
        "subject": "Completely new question",
        "body": "I have a new issue.",
        "message_id": "<new-ticket-email@mail.example>",
    }])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1

    tickets = db.query(Ticket).filter(Ticket.source == "email").all()
    assert len(tickets) == 1
    assert tickets[0].subject == "Completely new question"


def test_duplicate_message_id_skipped(db, client_org, customer_user, service):
    """
    Delivering the same Message-ID twice: second delivery is skipped
    (dedup via email_log), so no duplicate reply or ticket is created.
    """
    from app.services.email_piping import process_inbox
    from app.models.ticket import Ticket, TicketReply

    ticket = _seed_ticket(db, client_org, customer_user, service)
    original_mid = "<dedup-original@osd.vn>"
    _seed_thread(db, ticket.id, original_mid, direction="outbound")

    email_payload = {
        "from_addr": customer_user.email,
        "subject": "Re: Original issue",
        "body": "This is a duplicate.",
        "message_id": "<dup-inbound@mail.example>",
        "in_reply_to": original_mid,
    }

    mock_mail1 = _mock_imap([email_payload])
    with patch("imaplib.IMAP4_SSL", return_value=mock_mail1):
        count1 = process_inbox(db)

    # Same message_id a second time
    mock_mail2 = _mock_imap([email_payload])
    with patch("imaplib.IMAP4_SSL", return_value=mock_mail2):
        count2 = process_inbox(db)

    assert count1 == 1
    assert count2 == 0  # deduped

    # Only one reply should exist
    replies = db.query(TicketReply).filter(TicketReply.ticket_id == ticket.id).all()
    assert len(replies) == 1

    # EmailLog should record the skip
    from app.models.notification import EmailLog
    skipped = db.query(EmailLog).filter(
        EmailLog.action == "skipped",
        EmailLog.detail == "duplicate message_id",
    ).first()
    assert skipped is not None


def test_in_reply_to_takes_priority_over_subject(db, client_org, customer_user, service):
    """
    When both In-Reply-To header and [#N] subject tag are present but disagree,
    the In-Reply-To header wins (priority 1 > priority 3).
    """
    from app.services.email_piping import process_inbox
    from app.models.ticket import Ticket, TicketReply

    # Two distinct tickets
    ticket_a = _seed_ticket(db, client_org, customer_user, service)
    ticket_b = Ticket(
        org_id=client_org.id, service_id=service.id,
        subject="Another ticket", status="Open", raised_by=customer_user.id,
    )
    db.add(ticket_b)
    db.commit()
    db.refresh(ticket_b)

    # EmailThread ties the message_id to ticket_a
    original_mid = "<original-a@osd.vn>"
    _seed_thread(db, ticket_a.id, original_mid, direction="outbound")

    # Email has In-Reply-To → ticket_a, but [#ticket_b.id] in subject
    mock_mail = _mock_imap([{
        "from_addr": customer_user.email,
        "subject": f"Re: [#{ticket_b.id}] Something else",
        "body": "Confused subject, correct header.",
        "message_id": "<priority-test@mail.example>",
        "in_reply_to": original_mid,
    }])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        count = process_inbox(db)

    assert count == 1

    # Reply must land on ticket_a (the In-Reply-To target), not ticket_b
    replies_a = db.query(TicketReply).filter(TicketReply.ticket_id == ticket_a.id).all()
    replies_b = db.query(TicketReply).filter(TicketReply.ticket_id == ticket_b.id).all()
    assert len(replies_a) == 1
    assert len(replies_b) == 0


def test_inbound_thread_record_created(db, client_org, customer_user, service):
    """
    After a new email creates a ticket, an EmailThread row with direction=inbound
    is persisted so that subsequent replies can thread off of it.
    """
    from app.services.email_piping import process_inbox
    from app.models.email_thread import EmailThread

    mock_mail = _mock_imap([{
        "from_addr": customer_user.email,
        "subject": "Thread record test",
        "body": "New issue.",
        "message_id": "<thread-record@mail.example>",
    }])

    with patch("imaplib.IMAP4_SSL", return_value=mock_mail):
        process_inbox(db)

    thread = db.query(EmailThread).filter(
        EmailThread.message_id == "<thread-record@mail.example>"
    ).first()
    assert thread is not None
    assert thread.direction == "inbound"
