"""Prompt injection detection for AI inputs."""
import logging
import re

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = re.compile(
    r"\b(?:ignore|reveal|bypass|forget\s+instructions?|show\s+all|system\s+prompt)\b",
    re.IGNORECASE,
)


def check_prompt_injection(text: str) -> bool:
    """Return True if text looks like a prompt injection attempt."""
    if _INJECTION_PATTERNS.search(text):
        logger.warning("Prompt injection detected in input (first 120 chars): %.120s", text)
        return True
    return False
