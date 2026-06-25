"""Async Groq API client for chat completions."""
import logging
from typing import Any

import httpx

from app import config

logger = logging.getLogger(__name__)

GROQ_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


class AIDisabledException(Exception):
    """Raised when AI_FEATURES_ENABLED is false."""


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    if not config.AI_FEATURES_ENABLED:
        raise AIDisabledException("AI features are disabled (AI_FEATURES_ENABLED=false)")

    model = model or config.AI_MODEL
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(GROQ_COMPLETIONS_URL, json=payload, headers=headers)
            logger.info("Groq API status_code=%s attempt=%s", resp.status_code, attempt)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            if attempt == 0:
                logger.warning("Groq API timeout, retrying once")
                continue
            raise

    raise RuntimeError("Groq API failed after retry")
