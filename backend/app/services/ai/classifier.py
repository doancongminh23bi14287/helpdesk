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
    "Classify the ticket and respond ONLY with valid JSON, no markdown, no explanation.\n\n"
    "Categories:\n"
    "- hosting: the hosting/server itself — uptime, performance, storage, infrastructure\n"
    "- domain: domain name, DNS, domain renewal or transfer\n"
    "- email: company email — sending, receiving, mailbox accounts\n"
    "- billing: invoices, payments, pricing, plan changes, subscription cycle\n"
    "- technical: application-level bugs — broken features, plugin errors, data/backup restore, UI glitches\n"
    "- security: suspected attack, SSL/certificate trust issues, phishing, data-protection questions\n"
    "- general: feedback, compliments, general sales questions not tied to a specific plan\n\n"
    "Priority:\n"
    "- low: no urgency, not blocked, can wait days\n"
    "- medium: normal impact, inconvenienced but not blocked or losing revenue\n"
    "- high: meaningfully blocked or losing money/reputation, not a full outage\n"
    "- urgent: full outage, active security incident, ongoing business-critical harm right now\n\n"
    "Examples:\n"
    'Ticket: "Em muốn hỏi cách đổi mật khẩu tài khoản quản trị."\n'
    '{"category": "general", "priority": "low", "confidence": 0.9, "reasoning": "Simple how-to question, no urgency"}\n\n'
    'Ticket: "Toàn bộ hệ thống email công ty bị hack, dữ liệu khách hàng có thể đã bị lộ, cần xử lý ngay lập tức."\n'
    '{"category": "security", "priority": "urgent", "confidence": 0.95, "reasoning": "Active security incident with data breach risk"}\n\n'
    'Ticket: "Trang chủ load hơi chậm hơn bình thường một chút, không ảnh hưởng nhiều."\n'
    '{"category": "hosting", "priority": "low", "confidence": 0.8, "reasoning": "Minor performance issue, not blocking"}\n\n'
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

    subject_clean = sanitize_for_ai(subject or "")
    description_clean = sanitize_for_ai(description or "")
    injected = check_prompt_injection(subject_clean + " " + description_clean)

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
        {
            "role": "user",
            "content": f"Subject: {subject_clean}\nDescription: {description_clean or '(no description)'}",
        },
    ]

    try:
        raw = await groq_client.chat_completion(
            messages,
            temperature=0.2,
            max_tokens=256,
        )
    except groq_client.AIProviderTransientError:
        # Celery owns delayed retry; do not convert a retryable failure to None.
        raise
    except (
        groq_client.AIDisabledException,
        groq_client.AIProviderPermanentError,
    ) as exc:
        logger.warning(
            "AI classification unavailable ticket_id=%s category=%s",
            ticket_id,
            type(exc).__name__,
        )
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
        raw_response=None,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    logger.info(
        "Classified ticket_id=%s → category=%s priority=%s confidence=%.2f",
        ticket_id, category, priority, confidence,
    )
    return AiPredictionOut.model_validate(prediction)
