"""Referral endpoints."""

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import CurrentUserDep, SessionDep, SettingsDep
from app.schemas.referral import ReferralCreate, ReferralOut, StatusUpdate
from app.services.referral import (
    create_referral,
    get_visible_referral,
    list_referrals,
    to_out,
    transition_referral,
)

router = APIRouter(tags=["referrals"])


@router.post("/referrals", response_model=ReferralOut, status_code=201)
def post_referral(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep, body: ReferralCreate
) -> ReferralOut:
    """Create one referral for the caller's own assessment.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.
        body: Creation request.

    Returns:
        Created referral in clinician review.
    """
    referral = create_referral(session, user, body, settings.field_encryption_key)
    return to_out(session, referral, settings.field_encryption_key)


@router.get("/referrals", response_model=list[ReferralOut])
def get_referrals(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep
) -> list[ReferralOut]:
    """List referrals visible to the caller.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.

    Returns:
        Own referrals for users, all referrals for staff roles.
    """
    rows = list_referrals(session, user)
    return [to_out(session, row, settings.field_encryption_key) for row in rows]


@router.get("/referrals/{referral_id}", response_model=ReferralOut)
def get_referral(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep, referral_id: UUID
) -> ReferralOut:
    """Return one visible referral.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.
        referral_id: Referral id.

    Returns:
        Referral with transition history.
    """
    row = get_visible_referral(session, user, referral_id)
    return to_out(session, row, settings.field_encryption_key)


@router.patch("/referrals/{referral_id}/status", response_model=ReferralOut)
def patch_referral_status(
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    referral_id: UUID,
    body: StatusUpdate,
) -> ReferralOut:
    """Move one referral to a new status.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.
        referral_id: Referral id.
        body: Transition request.

    Returns:
        Updated referral.
    """
    row = get_visible_referral(session, user, referral_id)
    updated = transition_referral(
        session,
        row,
        user,
        body.to_status,
        settings.field_encryption_key,
        appointment_time=body.appointment_time,
        outcome_note=body.outcome_note,
    )
    return to_out(session, updated, settings.field_encryption_key)
