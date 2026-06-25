"""Sanitize user-supplied text before sending to AI."""
import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_VN_RE = re.compile(r"(?<!\d)(0|\+84)(3[2-9]|5[6-9]|7[06-9]|8[0-9]|9[0-9])\d{7}(?!\d)")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SECRET_RE = re.compile(
    r"(?:password|secret|key|token|passwd|pwd)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def sanitize_for_ai(text: str) -> str:
    text = _SECRET_RE.sub("[SECRET]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_VN_RE.sub("[PHONE]", text)
    text = _IP_RE.sub("[IP]", text)
    return text
