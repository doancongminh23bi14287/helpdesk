"""Tests for AI reply suggestion endpoints."""
import pytest
from unittest.mock import AsyncMock, patch


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def ticket_for_reply(db, client_org, service):
    from app.models.ticket import Ticket
    t = Ticket(
        org_id=client_org.id,
        service_id=service.id,
        subject="Help with billing",
        description="I was charged twice for my subscription.",
        status="Open",
        priority="High",
        ticket_type="Complaint",
        source="portal",
        raised_by_email="c@test.com",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _mock_groq(text="Xin chào, chúng tôi đã nhận được yêu cầu của bạn."):
    return patch(
        "app.services.ai.groq_client.chat_completion",
        new=AsyncMock(return_value=text),
    )


def test_suggest_reply_staff(client, staff_token, staff_assignment, ticket_for_reply):
    """Staff can request a reply suggestion."""
    import app.config as cfg
    original = cfg.AI_FEATURES_ENABLED
    cfg.AI_FEATURES_ENABLED = True
    try:
        with _mock_groq():
            r = client.post(
                f"/api/ai/tickets/{ticket_for_reply.id}/suggest-reply",
                headers=auth(staff_token),
            )
        assert r.status_code == 200
        data = r.json()
        assert data["ticket_id"] == ticket_for_reply.id
        assert len(data["generated_text"]) > 0
        assert data["accepted"] is False
        assert data["edited"] is False
    finally:
        cfg.AI_FEATURES_ENABLED = original


def test_suggest_reply_customer_forbidden(client, customer_token, ticket_for_reply):
    """Customer cannot request reply suggestions."""
    r = client.post(
        f"/api/ai/tickets/{ticket_for_reply.id}/suggest-reply",
        headers=auth(customer_token),
    )
    assert r.status_code == 403


def test_accept_suggestion(client, staff_token, staff_assignment, ticket_for_reply, db):
    """PATCH accept sets accepted=True."""
    import app.config as cfg
    original = cfg.AI_FEATURES_ENABLED
    cfg.AI_FEATURES_ENABLED = True
    try:
        with _mock_groq():
            create_r = client.post(
                f"/api/ai/tickets/{ticket_for_reply.id}/suggest-reply",
                headers=auth(staff_token),
            )
        assert create_r.status_code == 200
        suggestion_id = create_r.json()["id"]

        accept_r = client.patch(
            f"/api/ai/suggestions/{suggestion_id}/accept",
            headers=auth(staff_token),
            json={},
        )
        assert accept_r.status_code == 200
        assert accept_r.json()["accepted"] is True
    finally:
        cfg.AI_FEATURES_ENABLED = original


def test_list_suggestions_empty(client, staff_token, staff_assignment, ticket_for_reply):
    """Ticket with no suggestions returns empty list."""
    r = client.get(
        f"/api/ai/tickets/{ticket_for_reply.id}/suggestions",
        headers=auth(staff_token),
    )
    assert r.status_code == 200
    assert r.json() == []


def test_list_suggestions_after_create(client, staff_token, staff_assignment, ticket_for_reply):
    """After creating a suggestion, it appears in the list."""
    import app.config as cfg
    original = cfg.AI_FEATURES_ENABLED
    cfg.AI_FEATURES_ENABLED = True
    try:
        with _mock_groq("Đây là câu trả lời gợi ý."):
            client.post(
                f"/api/ai/tickets/{ticket_for_reply.id}/suggest-reply",
                headers=auth(staff_token),
            )

        r = client.get(
            f"/api/ai/tickets/{ticket_for_reply.id}/suggestions",
            headers=auth(staff_token),
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert items[0]["ticket_id"] == ticket_for_reply.id
    finally:
        cfg.AI_FEATURES_ENABLED = original
