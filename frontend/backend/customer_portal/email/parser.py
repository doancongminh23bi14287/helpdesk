"""
Email parser — converts raw RFC 2822 email bytes into a structured dict.
Handles multi-part MIME, encoded headers, and attachment extraction.
No Frappe dependencies; this module is pure Python for easy unit testing.
"""
import email
import email.policy
from email.header import decode_header
from typing import Optional


def parse_raw_email(raw_bytes: bytes) -> dict:
    """
    Parse raw email bytes and return a normalised dict:

    {
        message_id   : str                 — e.g. "abc@mail.example.com"
        in_reply_to  : str | None          — parent Message-ID (for threading)
        references   : list[str]           — full ancestor chain
        from_email   : str                 — sender address
        to_emails    : list[str]           — recipient addresses
        subject      : str
        body_text    : str                 — plain-text body (may be empty)
        body_html    : str | None          — HTML body
        attachments  : list[dict]          — {filename, content_type, data}
    }
    """
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

    return {
        "message_id":  _clean_msg_id(msg.get("Message-ID", "")),
        "in_reply_to": _clean_msg_id(msg.get("In-Reply-To", "")) or None,
        "references":  _parse_references(msg.get("References", "")),
        "from_email":  _extract_addr(msg.get("From", "")),
        "to_emails":   [_extract_addr(a) for a in (msg.get("To", "") or "").split(",") if a.strip()],
        "subject":     _decode_words(msg.get("Subject", "(no subject)")),
        "body_text":   _text_body(msg),
        "body_html":   _html_body(msg),
        "attachments": _attachments(msg),
    }


# ── Private ───────────────────────────────────────────────────────────────────

def _clean_msg_id(value: str) -> str:
    return value.strip().strip("<>")


def _decode_words(raw: str) -> str:
    """Decode RFC 2047 encoded-word sequences in header values."""
    parts = decode_header(raw or "")
    decoded = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(chunk or "")
    return "".join(decoded).strip()


def _extract_addr(addr: str) -> str:
    """Extract bare email address from 'Display Name <addr>' format."""
    import re
    m = re.search(r"<([^>]+)>", addr)
    return (m.group(1) if m else addr).strip().lower()


def _parse_references(raw: str) -> list:
    """Split References header into a list of clean Message-IDs."""
    return [_clean_msg_id(r) for r in raw.split() if r.strip()]


def _text_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            try:
                return part.get_content() or ""
            except Exception:
                return part.get_payload(decode=True).decode("utf-8", errors="replace")
    return ""


def _html_body(msg) -> Optional[str]:
    for part in msg.walk():
        if part.get_content_type() == "text/html" and not part.get_filename():
            try:
                return part.get_content()
            except Exception:
                return part.get_payload(decode=True).decode("utf-8", errors="replace")
    return None


def _attachments(msg) -> list:
    result = []
    for part in msg.walk():
        filename = part.get_filename()
        if filename:
            result.append({
                "filename":     _decode_words(filename),
                "content_type": part.get_content_type(),
                "data":         part.get_payload(decode=True),
            })
    return result
