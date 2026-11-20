"""Share endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUserDep, SessionDep, require_consent
from app.core.enums import ConsentScope
from app.models import Share, User
from app.schemas.share import ShareCreate, ShareOut, ShareScope
from app.services.share import create_share, list_shares, revoke_share

router = APIRouter(tags=["shares"])

ConsentedShareUser = Annotated[User, Depends(require_consent(ConsentScope.SHARE_WITH_CLINICIAN))]


def _to_out(share: Share) -> ShareOut:
    """Build a share response.

    Args:
        share: Share row.

    Returns:
        Share response.
    """
    return ShareOut(
        id=share.id,
        recipient_id=share.recipient_id,
        scope=ShareScope.model_validate(share.scope),
        expires_at=share.expires_at,
        revoked_at=share.revoked_at,
        created_at=share.created_at,
    )


@router.post("/shares", response_model=ShareOut, status_code=201)
def post_share(user: ConsentedShareUser, session: SessionDep, body: ShareCreate) -> ShareOut:
    """Grant one clinician record access.

    Args:
        user: Authenticated user with sharing consent.
        session: Request database session.
        body: Creation request.

    Returns:
        Created share.
    """
    share = create_share(session, user, body.recipient_id, body.scope, body.expires_in_hours)
    return _to_out(share)


@router.get("/shares", response_model=list[ShareOut])
def get_shares(user: CurrentUserDep, session: SessionDep) -> list[ShareOut]:
    """List the caller's share grants.

    Args:
        user: Authenticated user.
        session: Request database session.

    Returns:
        Share grants newest first.
    """
    return [_to_out(share) for share in list_shares(session, user)]


@router.delete("/shares/{share_id}", response_model=ShareOut)
def delete_share(user: CurrentUserDep, session: SessionDep, share_id: UUID) -> ShareOut:
    """Revoke one of the caller's shares.

    Args:
        user: Authenticated user.
        session: Request database session.
        share_id: Share id.

    Returns:
        Revoked share.
    """
    return _to_out(revoke_share(session, user, share_id))
