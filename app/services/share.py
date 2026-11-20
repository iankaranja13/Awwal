"""Share grant service with expiry-aware access checks."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.enums import Role
from app.core.errors import ForbiddenError, InvalidInputError, NotFoundError
from app.models import Share, User
from app.schemas.share import ShareScope
from app.services.audit import record as record_audit
from app.services.users import get_user


def create_share(
    session: Session,
    user: User,
    recipient_id: UUID,
    scope: ShareScope,
    expires_in_hours: int,
    now: datetime | None = None,
) -> Share:
    """Grant one clinician record access.

    Args:
        session: Database session.
        user: Granting user.
        recipient_id: Clinician recipient id.
        scope: Share scope.
        expires_in_hours: Lifetime in hours.
        now: Timestamp override for deterministic tests.

    Returns:
        Created share (flushed; committed by the caller).

    Raises:
        NotFoundError: If the recipient is missing.
        InvalidInputError: If the recipient is not a clinician.
    """
    recipient = get_user(session, recipient_id)
    if recipient is None:
        raise NotFoundError("Recipient not found.")
    if recipient.role != Role.CLINICIAN:
        raise InvalidInputError("Shares can only go to clinicians.")
    moment = now if now is not None else utc_now()
    share = Share(
        user_id=user.id,
        recipient_id=recipient.id,
        scope=scope.model_dump(mode="json"),
        expires_at=moment + timedelta(hours=expires_in_hours),
        created_at=moment,
    )
    session.add(share)
    session.flush()
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="share.created",
        object_type="share",
        object_id=share.id,
        detail={"recipient": str(recipient.id)},
        now=moment,
    )
    return share


def revoke_share(session: Session, user: User, share_id: UUID) -> Share:
    """Revoke one of the caller's shares.

    Args:
        session: Database session.
        user: Granting user.
        share_id: Share id.

    Returns:
        Revoked share.

    Raises:
        NotFoundError: If the share is missing or belongs to someone else.
    """
    share = session.get(Share, share_id)
    if share is None or share.user_id != user.id:
        raise NotFoundError("Share not found.")
    share.revoked_at = utc_now()
    session.flush()
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="share.revoked",
        object_type="share",
        object_id=share.id,
    )
    return share


def list_shares(session: Session, user: User) -> list[Share]:
    """List one user's share grants, newest first.

    Args:
        session: Database session.
        user: Granting user.

    Returns:
        Share grants.
    """
    return list(
        session.scalars(
            select(Share)
            .where(Share.user_id == user.id)
            .order_by(Share.created_at.desc(), Share.id.desc())
        ).all()
    )


def active_shares(session: Session, user_id: UUID, recipient_id: UUID) -> list[Share]:
    """List active shares from one user to one recipient.

    Expiry is compared in the database so backend clocks stay consistent.

    Args:
        session: Database session.
        user_id: Granting user id.
        recipient_id: Recipient id.

    Returns:
        Unexpired, unrevoked shares.
    """
    return list(
        session.scalars(
            select(Share).where(
                Share.user_id == user_id,
                Share.recipient_id == recipient_id,
                Share.revoked_at.is_(None),
                Share.expires_at > func.now(),
            )
        ).all()
    )


def has_active_share(
    session: Session, user_id: UUID, recipient_id: UUID, assessment_id: UUID | None
) -> bool:
    """Check whether an active share covers one assessment.

    Args:
        session: Database session.
        user_id: Granting user id.
        recipient_id: Recipient id.
        assessment_id: Assessment id (None asks for whole-record scope).

    Returns:
        True when an active all-scope share exists, or an ids-scope share
        covers the assessment (whole-record access needs all-scope).
    """
    for share in active_shares(session, user_id, recipient_id):
        scope = ShareScope.model_validate(share.scope)
        if scope.all:
            return True
        if assessment_id is not None and assessment_id in scope.assessment_ids:
            return True
    return False


def require_shared_assessment(
    session: Session, clinician: User, owner_id: UUID, assessment_id: UUID
) -> None:
    """Enforce shared access to one assessment.

    Args:
        session: Database session.
        clinician: Requesting clinician.
        owner_id: Owning user id.
        assessment_id: Assessment id.

    Raises:
        ForbiddenError: If no active share covers the assessment.
    """
    if clinician.role != Role.CLINICIAN:
        raise ForbiddenError("Only clinicians use shared access.")
    if not has_active_share(session, owner_id, clinician.id, assessment_id):
        raise ForbiddenError("No active share covers this record.")
