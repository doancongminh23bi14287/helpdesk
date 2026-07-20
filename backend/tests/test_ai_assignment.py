from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.config import settings
from app.core.security import hash_password
from app.models.ai_prediction import TicketAiPrediction
from app.models.team import StaffOrgAssignment
from app.models.ticket import Ticket, TicketActivity, TicketAssignee, TicketReply
from app.models.user import User
from app.services.ai_assignment import reevaluate_assignment_after_prediction


def _ticket_and_prediction(
    db,
    admin_user,
    staff_user,
    client_org,
    *,
    confidence=0.95,
    assignment_mode="auto",
):
    ticket = Ticket(
        org_id=client_org.id,
        subject="AI routing test",
        status="Open",
        priority="Medium",
        ticket_type="Question",
        source="portal",
        raised_by=admin_user.id,
        assignee_id=staff_user.id,
        assignment_mode=assignment_mode,
    )
    db.add(ticket)
    db.flush()
    db.add(TicketAssignee(
        ticket_id=ticket.id,
        user_id=staff_user.id,
        is_primary=True,
    ))
    prediction = TicketAiPrediction(
        ticket_id=ticket.id,
        predicted_category="hosting",
        predicted_priority="high",
        confidence=confidence,
        model_name="test-model",
        model_version="1",
    )
    db.add(prediction)
    db.commit()
    db.refresh(ticket)
    db.refresh(prediction)
    return ticket, prediction


def _second_eligible_staff(db, provider_org, client_org, email="ai-route-2@test.com"):
    user = User(
        org_id=provider_org.id,
        email=email,
        password_hash=hash_password("secret"),
        full_name="AI Route Two",
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(StaffOrgAssignment(user_id=user.id, org_id=client_org.id))
    db.commit()
    db.refresh(user)
    return user


def _scores(current, best):
    return [
        {
            "user_id": best.id,
            "full_name": best.full_name,
            "total_score": 90.0,
            "last_assigned_at": None,
        },
        {
            "user_id": current.id,
            "full_name": current.full_name,
            "total_score": 50.0,
            "last_assigned_at": None,
        },
    ]


def _evaluation_patches(mode, scores):
    return (
        patch.object(settings, "AI_ASSIGNMENT_REEVALUATION_ENABLED", True),
        patch.object(settings, "AI_ASSIGNMENT_REEVALUATION_MODE", mode),
        patch.object(settings, "AI_ASSIGNMENT_CONFIDENCE_THRESHOLD", 0.75),
        patch.object(settings, "AI_ASSIGNMENT_MIN_SCORE_IMPROVEMENT", 8.0),
        patch.object(settings, "AI_ASSIGNMENT_MAX_TICKET_AGE_MINUTES", 5),
        patch(
            "app.services.ai_assignment.acquire_assignment_lock",
            return_value=("assignment:org:test", "owner", True),
        ),
        patch("app.services.ai_assignment._release_assignment_lock"),
        patch("app.services.ai_assignment.score_breakdown", return_value=scores),
    )


def _run_with_patches(ticket, prediction, db, mode, scores):
    patches = _evaluation_patches(mode, scores)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        return reevaluate_assignment_after_prediction(ticket.id, prediction.id, db)


def test_high_confidence_prediction_creates_recommendation_without_reassignment(
    db, admin_user, staff_user, staff_assignment, client_org, provider_org
):
    best = _second_eligible_staff(db, provider_org, client_org)
    ticket, prediction = _ticket_and_prediction(
        db, admin_user, staff_user, client_org
    )

    result = _run_with_patches(
        ticket, prediction, db, "suggest", _scores(staff_user, best)
    )

    db.refresh(ticket)
    assert result["outcome"] == "recommended"
    assert result["recommended_user_id"] == best.id
    assert ticket.assignee_id == staff_user.id
    assert db.query(TicketActivity).filter(
        TicketActivity.ticket_id == ticket.id,
        TicketActivity.action == "ai_assignment_recommended",
        TicketActivity.to_value == str(best.id),
    ).count() == 1


def test_repeated_prediction_evaluation_is_idempotent(
    db, admin_user, staff_user, staff_assignment, client_org, provider_org
):
    best = _second_eligible_staff(db, provider_org, client_org)
    ticket, prediction = _ticket_and_prediction(
        db, admin_user, staff_user, client_org
    )
    scores = _scores(staff_user, best)

    first = _run_with_patches(ticket, prediction, db, "suggest", scores)
    second = _run_with_patches(ticket, prediction, db, "suggest", scores)

    assert first["outcome"] == "recommended"
    assert second["outcome"] == "already_evaluated"
    assert db.query(TicketActivity).filter(
        TicketActivity.ticket_id == ticket.id,
        TicketActivity.action == "ai_assignment_recommended",
    ).count() == 1


def test_auto_mode_reassigns_and_records_complete_activity(
    db, admin_user, staff_user, staff_assignment, client_org, provider_org
):
    best = _second_eligible_staff(db, provider_org, client_org)
    ticket, prediction = _ticket_and_prediction(
        db, admin_user, staff_user, client_org
    )

    result = _run_with_patches(
        ticket, prediction, db, "auto", _scores(staff_user, best)
    )

    db.refresh(ticket)
    assert result["outcome"] == "reassigned"
    assert ticket.assignee_id == best.id
    activity = db.query(TicketActivity).filter(
        TicketActivity.ticket_id == ticket.id,
        TicketActivity.action == "ai_guarded_reassigned",
    ).one()
    assert activity.from_value == str(staff_user.id)
    assert activity.to_value == str(best.id)


def test_low_confidence_prediction_never_reassigns(
    db, admin_user, staff_user, staff_assignment, client_org, provider_org
):
    best = _second_eligible_staff(db, provider_org, client_org)
    ticket, prediction = _ticket_and_prediction(
        db, admin_user, staff_user, client_org, confidence=0.5
    )

    result = _run_with_patches(
        ticket, prediction, db, "auto", _scores(staff_user, best)
    )

    db.refresh(ticket)
    assert result["outcome"] == "prediction_below_confidence_threshold"
    assert ticket.assignee_id == staff_user.id


@pytest.mark.parametrize("is_internal", [False, True])
def test_staff_reply_or_internal_note_blocks_reassignment(
    db,
    admin_user,
    staff_user,
    staff_assignment,
    client_org,
    provider_org,
    is_internal,
):
    best = _second_eligible_staff(
        db, provider_org, client_org, email=f"handled-{is_internal}@test.com"
    )
    ticket, prediction = _ticket_and_prediction(
        db, admin_user, staff_user, client_org
    )
    db.add(TicketReply(
        ticket_id=ticket.id,
        author_id=staff_user.id,
        content="Work has started",
        is_internal=is_internal,
        source="portal",
    ))
    db.commit()

    result = _run_with_patches(
        ticket, prediction, db, "auto", _scores(staff_user, best)
    )

    db.refresh(ticket)
    assert result["outcome"] == "staff_reply_or_internal_note_exists"
    assert ticket.assignee_id == staff_user.id


def test_manual_assignment_blocks_reassignment(
    db, admin_user, staff_user, staff_assignment, client_org, provider_org
):
    best = _second_eligible_staff(db, provider_org, client_org)
    ticket, prediction = _ticket_and_prediction(
        db,
        admin_user,
        staff_user,
        client_org,
        assignment_mode="manual",
    )

    result = _run_with_patches(
        ticket, prediction, db, "auto", _scores(staff_user, best)
    )

    assert result["outcome"] == "manual_or_non_auto_assignment"


def test_old_ticket_blocks_reassignment(
    db, admin_user, staff_user, staff_assignment, client_org, provider_org
):
    best = _second_eligible_staff(db, provider_org, client_org)
    ticket, prediction = _ticket_and_prediction(
        db, admin_user, staff_user, client_org
    )
    ticket.created_at = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    )
    db.commit()

    result = _run_with_patches(
        ticket, prediction, db, "auto", _scores(staff_user, best)
    )

    assert result["outcome"] == "ticket_too_old"


def test_repeated_celery_delivery_reuses_existing_prediction(
    db, admin_user, staff_user, staff_assignment, client_org
):
    from app.tasks.ai_tasks import classify_ticket_task
    from tests.conftest import TestingSessionLocal

    ticket, prediction = _ticket_and_prediction(
        db, admin_user, staff_user, client_org
    )
    with patch(
        "app.tasks.ai_tasks.SessionLocal",
        side_effect=TestingSessionLocal,
    ), patch(
        "app.services.ai.classifier.classify_ticket"
    ) as classify, patch(
        "app.services.ai_assignment.reevaluate_assignment_after_prediction",
        return_value={"outcome": "already_evaluated"},
    ) as evaluate:
        result = classify_ticket_task.run(ticket.id)

    classify.assert_not_called()
    evaluate.assert_called_once_with(ticket.id, prediction.id, evaluate.call_args.args[2])
    assert result["id"] == prediction.id
