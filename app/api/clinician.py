"""Clinician queue and review endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, SettingsDep, require_role
from app.core.enums import Role
from app.models import Assessment, User
from app.schemas.referral import QueueEntry, ReviewRequest, ReviewResponse
from app.services.review import queue_entries, submit_review
from app.services.users import get_user

router = APIRouter(tags=["clinician"])

ClinicianUser = Annotated[User, Depends(require_role(Role.CLINICIAN))]


@router.get("/clinician/queue", response_model=list[QueueEntry])
def get_queue(user: ClinicianUser, session: SessionDep) -> list[QueueEntry]:
    """List referrals awaiting clinician review.

    Args:
        user: Authenticated clinician (unused beyond authorisation).
        session: Request database session.

    Returns:
        Queue entries oldest first.
    """
    _ = user
    entries: list[QueueEntry] = []
    for referral in queue_entries(session):
        owner = get_user(session, referral.user_id)
        handle = owner.pseudonymous_handle if owner is not None else "unknown"
        assessment = session.get(Assessment, referral.assessment_id)
        route = assessment.route.value if assessment is not None else "unknown"
        entries.append(
            QueueEntry(
                referral_id=referral.id,
                assessment_id=referral.assessment_id,
                user_handle=handle,
                type=referral.type,
                status=referral.status,
                route=route,
                created_at=referral.created_at,
            )
        )
    return entries


@router.post("/clinician/review", response_model=ReviewResponse)
def post_review(
    user: ClinicianUser, session: SessionDep, settings: SettingsDep, body: ReviewRequest
) -> ReviewResponse:
    """Record one clinician review and move its referral.

    Args:
        user: Authenticated clinician.
        session: Request database session.
        settings: Application settings.
        body: Review request.

    Returns:
        Stored review with referral outcome.
    """
    review, referral = submit_review(
        session,
        user,
        body.assessment_id,
        body.decision,
        body.edits,
        body.notes,
        settings.field_encryption_key,
    )
    return ReviewResponse(
        id=review.id,
        assessment_id=review.assessment_id,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        signed_off_at=review.signed_off_at,
        referral_id=referral.id,
        referral_status=referral.status,
    )
