"""AI ticket classification service."""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app import config
from app.models.ai_prediction import TicketAiPrediction
from app.schemas.ai import AiPredictionOut
from app.services.ai.sanitizer import sanitize_for_ai
from app.services.ai.prompt_guard import check_prompt_injection
from app.services.ai import groq_client

logger = logging.getLogger(__name__)

_VALID_PRIORITIES = {"urgent", "high", "medium", "low"}
_VALID_CATEGORIES = {"hosting", "domain", "email", "billing", "technical", "security", "general"}

_SYSTEM_PROMPT = (
    "You are a helpdesk ticket classifier for a Vietnamese web hosting provider. "
    "Classify the ticket and respond ONLY with valid JSON, no markdown, no explanation.\n"
    "Valid priorities: urgent, high, medium, low\n"
    "Valid categories: hosting, domain, email, billing, technical, security, general\n"
    'Expected JSON: {"category": "...", "priority": "...", "confidence": 0.0, "reasoning": "..."}'
)


async def classify_ticket(
    *,
    ticket_id: int,
    subject: str,
    description: str,
    ticket_type: str,
    org_id: int,
    db: Session,
) -> Optional[AiPredictionOut]:
    if not config.AI_FEATURES_ENABLED:
        return None

    sanitized = sanitize_for_ai((subject or "") + " " + (description or ""))
    injected = check_prompt_injection(sanitized)

    if injected:
        prediction = TicketAiPrediction(
            ticket_id=ticket_id,
            predicted_category="unclassified",
            predicted_priority="medium",
            confidence=0.0,
            model_name=config.AI_MODEL,
            model_version="1.0",
            raw_response=None,
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
        return AiPredictionOut.model_validate(prediction)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Subject: {subject}\nDescription: {description or '(no description)'}"},
    ]

    try:
        raw = await groq_client.chat_completion(
            messages,
            temperature=0.2,
            max_tokens=256,
        )
    except Exception:
        logger.exception("Groq API call failed for ticket_id=%s", ticket_id)
        return None

    try:
        parsed = json.loads(raw)
        category = str(parsed.get("category", "general")).lower().strip()
        priority = str(parsed.get("priority", "medium")).lower().strip()
        confidence = float(parsed.get("confidence", 0.5))
        reasoning = str(parsed.get("reasoning", ""))
    except (json.JSONDecodeError, ValueError, AttributeError):
        logger.warning("Failed to parse Groq JSON response for ticket_id=%s: %.200s", ticket_id, raw)
        return None

    if category not in _VALID_CATEGORIES:
        category = "general"
    if priority not in _VALID_PRIORITIES:
        priority = "medium"
    confidence = max(0.0, min(1.0, confidence))

    prediction = TicketAiPrediction(
        ticket_id=ticket_id,
        predicted_category=category,
        predicted_priority=priority,
        confidence=confidence,
        model_name=config.AI_MODEL,
        model_version="1.0",
        raw_response=raw[:4000] if raw else None,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    logger.info(
        "Classified ticket_id=%s → category=%s priority=%s confidence=%.2f",
        ticket_id, category, priority, confidence,
    )
    return AiPredictionOut.model_validate(prediction)
