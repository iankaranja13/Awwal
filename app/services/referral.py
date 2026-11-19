"""Referral lifecycle service with role-gated transitions."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.crypto import decrypt_json, encrypt_json
from app.core.enums import ConsentScope, ReferralStatus, Role, Route
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    InvalidTransitionError,
    NotFoundError,
)
from app.models import ClinicianReview, Referral, ReferralEvent, Reminder, User
from app.schemas.referral import ReferralCreate, ReferralEventOut, ReferralOut
from app.services.assessment import get_own_assessment
from app.services.audit import record as record_audit
from app.services.consent import has_consent
from app.services.provider import get_provider

TERMINAL_STATUSES = frozenset({ReferralStatus.CLOSED, ReferralStatus.CANCELLED})
BOOKABLE_ROUTES = frozenset(
    {Route.ANDROLOGY_UROLOGY, Route.FERTILITY_SERVICES, Route.PRIMARY_CARE}
)

TRANSITIONS: dict[tuple[ReferralStatus, ReferralStatus], frozenset[Role]] = {
    (ReferralStatus.CLINICIAN_REVIEW, ReferralStatus.CONFIRMED): frozenset({Role.CLINICIAN}),
    (ReferralStatus.CLINICIAN_REVIEW, ReferralStatus.CANCELLED): frozenset(
        {Role.CLINICIAN, Role.USER}
    ),
    (ReferralStatus.CONFIRMED, ReferralStatus.BOOKED): frozenset({Role.USER, Role.NAVIGATOR}),
    (ReferralStatus.BOOKED, ReferralStatus.ATTENDED): frozenset(
        {Role.NAVIGATOR, Role.CLINICIAN}
    ),
    (ReferralStatus.BOOKED, ReferralStatus.NO_SHOW): frozenset({Role.NAVIGATOR}),
    (ReferralStatus.BOOKED, ReferralStatus.CANCELLED): frozenset({Role.USER, Role.NAVIGATOR}),
    (ReferralStatus.ATTENDED, ReferralStatus.RESULT_EXPLAINED): frozenset({Role.CLINICIAN}),
    (ReferralStatus.RESULT_EXPLAINED, ReferralStatus.CLOSED): frozenset({Role.CLINICIAN}),
    (ReferralStatus.NO_SHOW, ReferralStatus.BOOKED): frozenset({Role.NAVIGATOR}),
}


def get_visible_referral(session: Session, user: User, referral_id: UUID) -> Referral:
    """Load one referral visible to the caller.

    Args:
        session: Database session.
        user: Authenticated user.
        referral_id: Referral id.

    Returns:
        The referral row.

    Raises:
        NotFoundError: If the referral is missing or belongs to someone else.
    """
    row = session.get(Referral, referral_id)
    if row is None:
        raise NotFoundError("Referral not found.")
    if user.role == Role.USER and row.user_id != user.id:
        raise NotFoundError("Referral not found.")
    return row


def list_referrals(session: Session, user: User) -> list[Referral]:
    """List referrals visible to the caller.

    Args:
        session: Database session.
        user: Authenticated user.

    Returns:
        Own referrals for users, all referrals for staff roles.
    """
    query = select(Referral).order_by(Referral.created_at.desc())
    if user.role == Role.USER:
        query = query.where(Referral.user_id == user.id)
    return list(session.scalars(query).all())


def list_events(session: Session, referral_id: UUID) -> list[ReferralEvent]:
    """List transition events for one referral in order.

    Args:
        session: Database session.
        referral_id: Referral id.

    Returns:
        Events oldest first.
    """
    return list(
        session.scalars(
            select(ReferralEvent)
            .where(ReferralEvent.referral_id == referral_id)
            .order_by(ReferralEvent.at.asc(), ReferralEvent.id.asc())
        ).all()
    )


def to_outcome_note(encrypted: str | None, key: str) -> str | None:
    """Decrypt a stored outcome note.

    Args:
        encrypted: Stored ciphertext.
        key: Field encryption key.

    Returns:
        Plain note, or None when absent.
    """
    if encrypted is None:
        return None
    return str(decrypt_json(encrypted, key).get("note"))


def to_out(session: Session, referral: Referral, key: str) -> ReferralOut:
    """Build the API response for one referral.

    Args:
        session: Database session.
        referral: Referral row.
        key: Field encryption key.

    Returns:
        Referral response with decrypted note and events.
    """
    events = [
        ReferralEventOut(
            id=event.id,
            from_status=event.from_status,
            to_status=event.to_status,
            actor_id=event.actor_id,
            at=event.at,
        )
        for event in list_events(session, referral.id)
    ]
    return ReferralOut(
        id=referral.id,
        assessment_id=referral.assessment_id,
        user_id=referral.user_id,
        type=referral.type,
        provider_id=referral.provider_id,
        status=referral.status,
        preferred_time=referral.preferred_time,
        appointment_time=referral.appointment_time,
        outcome_note=to_outcome_note(referral.outcome_note_encrypted, key),
        created_at=referral.created_at,
        updated_at=referral.updated_at,
        events=events,
    )


def _require_future(value: datetime, moment: datetime, field: str) -> datetime:
    """Reject naive or past datetimes.

    Args:
        value: Submitted value.
        moment: Current time.
        field: Field name for error messages.

    Returns:
        The validated value.

    Raises:
        InvalidInputError: If the value lacks a timezone or is not future.
    """
    if value.tzinfo is None:
        raise InvalidInputError(f"{field} must include a timezone.")
    if value <= moment:
        raise InvalidInputError(f"{field} must be in the future.")
    return value


def _record_event(
    session: Session,
    referral_id: UUID,
    from_status: ReferralStatus | None,
    to_status: ReferralStatus,
    actor_id: UUID | None,
    moment: datetime,
) -> None:
    """Append one transition event.

    Args:
        session: Database session.
        referral_id: Referral id.
        from_status: Previous status (None at creation).
        to_status: New status.
        actor_id: Acting user id (None for system).
        moment: Transition time.
    """
    session.add(
        ReferralEvent(
            referral_id=referral_id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            at=moment,
        )
    )
    session.flush()


def create_referral(
    session: Session,
    user: User,
    data: ReferralCreate,
    key: str,
    now: datetime | None = None,
) -> Referral:
    """Create one referral and move it to clinician review.

    Args:
        session: Database session.
        user: Owning user.
        data: Creation request.
        key: Field encryption key.
        now: Timestamp override for deterministic tests.

    Returns:
        Created referral in clinician review.

    Raises:
        NotFoundError: If the assessment or provider is missing.
        InvalidInputError: If the route needs no booking or data is invalid.
        ConflictError: If an active referral exists for the assessment and type.
    """
    moment = now if now is not None else utc_now()
    assessment = get_own_assessment(session, user, data.assessment_id)
    if assessment.route not in BOOKABLE_ROUTES:
        raise InvalidInputError("This route needs no booking.")
    active = session.scalars(
        select(Referral.id).where(
            Referral.assessment_id == data.assessment_id,
            Referral.type == data.type,
            Referral.status.not_in(TERMINAL_STATUSES),
        )
    ).first()
    if active is not None:
        raise ConflictError("An active referral already exists for this assessment and type.")
    provider_id = None
    if data.provider_id is not None:
        provider = get_provider(session, data.provider_id)
        if provider is None:
            raise NotFoundError("Provider not found.")
        if provider.type != data.type:
            raise InvalidInputError("Provider does not offer this service type.")
        provider_id = provider.id
    preferred = None
    if data.preferred_time is not None:
        preferred = _require_future(data.preferred_time, moment, "preferred_time")
    if data.contact is not None and any(
        [data.contact.name, data.contact.phone, data.contact.email]
    ):
        user.contact_encrypted = encrypt_json(data.contact.model_dump(mode="json"), key)
    referral = Referral(
        assessment_id=assessment.id,
        user_id=user.id,
        type=data.type,
        provider_id=provider_id,
        status=ReferralStatus.PROPOSED,
        preferred_time=preferred,
        created_at=moment,
        updated_at=moment,
    )
    session.add(referral)
    session.flush()
    _record_event(session, referral.id, None, ReferralStatus.PROPOSED, user.id, moment)
    referral.status = ReferralStatus.CLINICIAN_REVIEW
    referral.updated_at = moment
    session.flush()
    # A microsecond later: the auto-transition genuinely follows creation, and
    # distinct stamps keep event order deterministic under timestamp ties.
    _record_event(
        session,
        referral.id,
        ReferralStatus.PROPOSED,
        ReferralStatus.CLINICIAN_REVIEW,
        None,
        moment + timedelta(microseconds=1),
    )
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="referral.created",
        object_type="referral",
        object_id=referral.id,
        detail={"type": data.type.value},
        now=moment,
    )
    return referral


def has_signed_review(session: Session, assessment_id: UUID) -> bool:
    """Check for a signed clinician review of one assessment.

    Args:
        session: Database session.
        assessment_id: Assessment id.

    Returns:
        True when a signed review row exists.
    """
    return (
        session.scalars(
            select(ClinicianReview.id).where(
                ClinicianReview.assessment_id == assessment_id,
                ClinicianReview.signed_off_at.is_not(None),
            )
        ).first()
        is not None
    )


def transition_referral(
    session: Session,
    referral: Referral,
    actor: User,
    to_status: ReferralStatus,
    key: str,
    appointment_time: datetime | None = None,
    outcome_note: str | None = None,
    now: datetime | None = None,
) -> Referral:
    """Move one referral to a new status with role and rule checks.

    Args:
        session: Database session.
        referral: Referral row.
        actor: Acting user.
        to_status: Target status.
        key: Field encryption key.
        appointment_time: Appointment time (required when booking).
        outcome_note: Outcome note (required when closing).
        now: Timestamp override for deterministic tests.

    Returns:
        Updated referral.

    Raises:
        InvalidTransitionError: If the move is not allowed or ungated.
        ForbiddenError: If the actor may not make this move.
        InvalidInputError: If required inputs are missing or invalid.
    """
    allowed = TRANSITIONS.get((referral.status, to_status))
    if allowed is None:
        raise InvalidTransitionError(
            f"Cannot move from {referral.status.value} to {to_status.value}."
        )
    if actor.role not in allowed:
        raise ForbiddenError("Role cannot make this transition.")
    if actor.role == Role.USER and referral.user_id != actor.id:
        raise ForbiddenError("Cannot change someone else's referral.")
    moment = now if now is not None else utc_now()
    if to_status == ReferralStatus.CONFIRMED and not has_signed_review(
        session, referral.assessment_id
    ):
        raise InvalidTransitionError("Confirmation needs clinician sign-off.")
    if to_status == ReferralStatus.BOOKED:
        if appointment_time is None:
            raise InvalidInputError("Booking needs an appointment time.")
        referral.appointment_time = _require_future(appointment_time, moment, "appointment_time")
    if to_status == ReferralStatus.CLOSED:
        if not outcome_note:
            raise InvalidInputError("Closing needs an outcome note.")
        referral.outcome_note_encrypted = encrypt_json({"note": outcome_note}, key)
    from_status = referral.status
    referral.status = to_status
    referral.updated_at = moment
    session.flush()
    _record_event(session, referral.id, from_status, to_status, actor.id, moment)
    record_audit(
        session,
        actor_id=actor.id,
        actor_role=actor.role,
        action="referral.transition",
        object_type="referral",
        object_id=referral.id,
        detail={"from": from_status.value, "to": to_status.value},
        now=moment,
    )
    if to_status == ReferralStatus.BOOKED and referral.appointment_time is not None:
        _reminders_for_booking(session, referral, moment, referral.appointment_time)
    if to_status == ReferralStatus.ATTENDED:
        _follow_up_reminder(session, referral, moment)
    return referral


def _reminders_for_booking(
    session: Session, referral: Referral, moment: datetime, appointment: datetime
) -> None:
    """Create booking reminders when reminders consent holds.

    Args:
        session: Database session.
        referral: Referral row.
        moment: Booking time.
        appointment: Appointment time.
    """
    if not has_consent(session, referral.user_id, ConsentScope.REMINDERS):
        return
    session.add(
        Reminder(
            referral_id=referral.id,
            kind="booking_confirmation",
            due_at=moment,
            simulated_sent_at=moment,
        )
    )
    session.add(
        Reminder(
            referral_id=referral.id,
            kind="pre_visit",
            due_at=appointment - timedelta(hours=24),
            simulated_sent_at=None,
        )
    )
    session.flush()


def _follow_up_reminder(session: Session, referral: Referral, moment: datetime) -> None:
    """Create a follow-up reminder when reminders consent holds.

    Args:
        session: Database session.
        referral: Referral row.
        moment: Attendance time.
    """
    if not has_consent(session, referral.user_id, ConsentScope.REMINDERS):
        return
    session.add(
        Reminder(
            referral_id=referral.id,
            kind="follow_up",
            due_at=moment + timedelta(days=7),
            simulated_sent_at=None,
        )
    )
    session.flush()
