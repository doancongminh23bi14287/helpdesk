"""Async Groq API client with explicit transient/permanent failures."""
import logging
from typing import Any

import httpx

from app import config

logger = logging.getLogger(__name__)

GROQ_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


class AIDisabledException(Exception):
    """Raised when AI_FEATURES_ENABLED is false."""


class AIProviderTransientError(Exception):
    """Timeout, connection, rate-limit, or temporary provider failure."""


class AIProviderPermanentError(Exception):
    """Request/auth/schema error that cannot succeed unchanged."""


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    if not config.AI_FEATURES_ENABLED:
        raise AIDisabledException(
            "AI features are disabled (AI_FEATURES_ENABLED=false)"
        )

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
                response = await client.post(
                    GROQ_COMPLETIONS_URL,
                    json=payload,
                    headers=headers,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt == 0:
                logger.warning(
                    "Groq transient network error category=%s; retrying once",
                    type(exc).__name__,
                )
                continue
            raise AIProviderTransientError(type(exc).__name__) from exc

        logger.info(
            "Groq API status_code=%s attempt=%s",
            response.status_code,
            attempt,
        )
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 0:
                logger.warning(
                    "Groq transient HTTP status=%s; retrying once",
                    response.status_code,
                )
                continue
            raise AIProviderTransientError(
                f"provider_http_{response.status_code}"
            )
        if response.status_code >= 400:
            raise AIProviderPermanentError(
                f"provider_http_{response.status_code}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIProviderPermanentError(
                "malformed_provider_response"
            ) from exc
        if not isinstance(content, str):
            raise AIProviderPermanentError("non_text_provider_response")
        return content

    raise AIProviderTransientError("provider_retry_exhausted")
