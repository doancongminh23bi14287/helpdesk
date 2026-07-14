"""AI reply suggestion service."""
import hashlib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app import config
from app.models.ai_prediction import AiReplySuggestion
from app.models.ticket import Ticket, TicketReply
from app.models.user import User
from app.schemas.ai import AiReplyOut
from app.services.ai.sanitizer import sanitize_for_ai
from app.services.ai.prompt_guard import check_prompt_injection
from app.services.ai import groq_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful customer support agent for a Vietnamese web hosting provider. "
    "Write a professional, empathetic reply in Vietnamese (unless the customer wrote in English). "
    "Be concise (under 150 words). Do not invent facts. Do not mention internal systems."
)


def _author_role(reply: TicketReply, db: Session) -> str:
    if reply.author_id:
        u = db.query(User).filter(User.id == reply.author_id).first()
        if u:
            return u.role if u.role in ("admin", "staff") else "customer"
    return "customer"


async def suggest_reply(
    *,
    ticket_id: int,
    org_id: int,
    requested_by_user_id: int,
    db: Session,
) -> Optional[AiReplyOut]:
    if not config.AI_FEATURES_ENABLED:
        return None

    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.org_id == org_id,
        Ticket.is_deleted == False,
    ).first()
    if not ticket:
        return None

    # Last 5 non-internal replies
    replies = (
        db.query(TicketReply)
        .filter(TicketReply.ticket_id == ticket_id, TicketReply.is_internal == False)
        .order_by(TicketReply.created_at.desc())
        .limit(5)
        .all()
    )
    replies = list(reversed(replies))

    subject_clean = sanitize_for_ai(ticket.subject or "")
    desc_clean = sanitize_for_ai(ticket.description or "")

    if check_prompt_injection(subject_clean + " " + desc_clean):
        logger.warning("Prompt injection detected in ticket_id=%s, skipping reply suggestion", ticket_id)
        return None

    context_parts = [
        f"Ticket subject: {subject_clean}",
        f"Description: {desc_clean}",
        f"Priority: {ticket.priority}",
        f"Status: {ticket.status}",
    ]

    if replies:
        context_parts.append("\nConversation history (oldest first):")
        for r in replies:
            role = _author_role(r, db)
            content_clean = sanitize_for_ai(r.content or "")
            if check_prompt_injection(content_clean):
                logger.warning(
                    "Prompt injection detected in reply history for ticket_id=%s; skipping suggestion",
                    ticket_id,
                )
                return None
            context_parts.append(f"[{role}]: {content_clean}")

    context_parts.append("\nWrite a helpful support reply:")
    user_content = "\n".join(context_parts)

    prompt_full = _SYSTEM_PROMPT + "\n" + user_content
    prompt_hash = hashlib.sha256(prompt_full.encode()).hexdigest()

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        generated = await groq_client.chat_completion(
            messages,
            temperature=0.5,
            max_tokens=300,
        )
    except Exception:
        logger.exception("Groq API failed for suggest_reply ticket_id=%s", ticket_id)
        return None

    suggestion = AiReplySuggestion(
        ticket_id=ticket_id,
        reply_id=None,
        prompt_snapshot_hash=prompt_hash,
        generated_text=generated,
        accepted=False,
        edited=False,
        created_by=requested_by_user_id,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return AiReplyOut.model_validate(suggestion)
