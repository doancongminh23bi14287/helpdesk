"""AI endpoints — classification + reply suggestion."""
import asyncio
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models.ai_prediction import TicketAiPrediction, AiReplySuggestion
from app.models.ticket import Ticket
from app.models.user import User
from app.core.deps import get_current_user, require_staff_or_admin
from app.core.scoping import get_accessible_org_ids
from app.schemas.ai import AiPredictionOut, AiReplyOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _assert_ticket_accessible(ticket_id: int, user: User, db: Session) -> Ticket:
    """Return ticket if user may access it, else 404."""
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.is_deleted == False,
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    org_ids = get_accessible_org_ids(user, db)
    if org_ids is not None and ticket.org_id not in org_ids:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket


# ── 1. GET /api/ai/health ─────────────────────────────────────────────────────

@router.get("/health")
def ai_health():
    return {
        "ai_enabled": config.AI_FEATURES_ENABLED,
        "model": config.AI_MODEL,
        "groq_configured": bool(config.GROQ_API_KEY),
    }


# ── 2. GET /api/ai/tickets/{ticket_id}/prediction ─────────────────────────────

@router.get("/tickets/{ticket_id}/prediction", response_model=AiPredictionOut)
def get_prediction(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    _assert_ticket_accessible(ticket_id, user, db)

    prediction = (
        db.query(TicketAiPrediction)
        .filter(TicketAiPrediction.ticket_id == ticket_id)
        .order_by(TicketAiPrediction.created_at.desc())
        .first()
    )
    if not prediction:
        raise HTTPException(status_code=404, detail="No prediction found for this ticket")
    return prediction


# ── 3. POST /api/ai/tickets/{ticket_id}/classify ──────────────────────────────

@router.post("/tickets/{ticket_id}/classify", response_model=AiPredictionOut)
def classify_ticket_now(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    ticket = _assert_ticket_accessible(ticket_id, user, db)

    from app.services.ai.classifier import classify_ticket

    result = asyncio.run(
        classify_ticket(
            ticket_id=ticket.id,
            subject=ticket.subject,
            description=ticket.description or "",
            ticket_type=ticket.ticket_type,
            org_id=ticket.org_id,
            db=db,
        )
    )
    if result is None:
        raise HTTPException(status_code=503, detail="AI classification unavailable")
    return result


# ── 4. POST /api/ai/tickets/{ticket_id}/suggest-reply ────────────────────────

@router.post("/tickets/{ticket_id}/suggest-reply", response_model=AiReplyOut)
def suggest_reply(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    ticket = _assert_ticket_accessible(ticket_id, user, db)

    from app.services.ai.reply_suggester import suggest_reply as _suggest

    result = asyncio.run(
        _suggest(
            ticket_id=ticket.id,
            org_id=ticket.org_id,
            requested_by_user_id=user.id,
            db=db,
        )
    )
    if result is None:
        raise HTTPException(status_code=503, detail="AI reply suggestion unavailable")
    return result


# ── 5. PATCH /api/ai/suggestions/{suggestion_id}/accept ──────────────────────

from pydantic import BaseModel


class AcceptSuggestionRequest(BaseModel):
    text: str | None = None


@router.patch("/suggestions/{suggestion_id}/accept", response_model=AiReplyOut)
def accept_suggestion(
    suggestion_id: int,
    body: AcceptSuggestionRequest = AcceptSuggestionRequest(),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    suggestion = db.query(AiReplySuggestion).filter(AiReplySuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # Verify the ticket is accessible
    _assert_ticket_accessible(suggestion.ticket_id, user, db)

    suggestion.accepted = True
    if body.text and body.text != suggestion.generated_text:
        suggestion.edited = True
        suggestion.generated_text = body.text
    db.commit()
    db.refresh(suggestion)
    return suggestion


# ── 6. GET /api/ai/tickets/{ticket_id}/suggestions ───────────────────────────

@router.get("/tickets/{ticket_id}/suggestions", response_model=List[AiReplyOut])
def list_suggestions(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    _assert_ticket_accessible(ticket_id, user, db)

    suggestions = (
        db.query(AiReplySuggestion)
        .filter(AiReplySuggestion.ticket_id == ticket_id)
        .order_by(AiReplySuggestion.created_at.desc())
        .all()
    )
    return suggestions
