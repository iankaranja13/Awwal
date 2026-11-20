"""Clinician review service with sign-off gating."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.crypto import encrypt_json
from app.core.enums import ReferralStatus, ReviewDecision, Role
from app.core.errors import ForbiddenError, NotFoundError
from app.models import ClinicianReview, Referral, User
from app.services.referral import transition_referral


def submit_review(
    session: Session,
    reviewer: User,
    assessment_id: UUID,
    decision: ReviewDecision,
    edits: dict[str, Any] | None,
    notes: str | None,
    key: str,
    now: datetime | None = None,
) -> tuple[ClinicianReview, Referral]:
    """Record one clinician review and move its referral.

    Approval signs off and confirms the referral; rejection cancels it.

    Args:
        session: Database session.
        reviewer: Reviewing clinician.
        assessment_id: Assessment id.
        decision: Review decision.
        edits: Structured edits, if any.
        notes: Review notes, if any (stored encrypted).
        key: Field encryption key.
        now: Timestamp override for deterministic tests.

    Returns:
        Review row with the updated referral.

    Raises:
        ForbiddenError: If the reviewer is not a clinician.
        NotFoundError: If no referral awaits review for the assessment.
    """
    if reviewer.role != Role.CLINICIAN:
        raise ForbiddenError("Only clinicians can review.")
    referral = session.scalars(
        select(Referral)
        .where(
            Referral.assessment_id == assessment_id,
            Referral.status == ReferralStatus.CLINICIAN_REVIEW,
        )
        .order_by(Referral.created_at.asc())
    ).first()
    if referral is None:
        raise NotFoundError("No referral awaiting review.")
    moment = now if now is not None else utc_now()
    review = ClinicianReview(
        assessment_id=assessment_id,
        reviewer_id=reviewer.id,
        decision=decision,
        edits=dict(edits) if edits is not None else None,
        notes_encrypted=encrypt_json({"note": notes}, key) if notes else None,
        signed_off_at=moment if decision == ReviewDecision.APPROVED else None,
    )
    session.add(review)
    session.flush()
    if decision == ReviewDecision.APPROVED:
        target = ReferralStatus.CONFIRMED
    else:
        target = ReferralStatus.CANCELLED
    updated = transition_referral(session, referral, reviewer, target, key, now=moment)
    return review, updated


def queue_entries(session: Session) -> list[Referral]:
    """List referrals awaiting clinician review, oldest first.

    Args:
        session: Database session.

    Returns:
        Referrals in clinician review.
    """
    return list(
        session.scalars(
            select(Referral)
            .where(Referral.status == ReferralStatus.CLINICIAN_REVIEW)
            .order_by(Referral.created_at.asc())
        ).all()
    )
