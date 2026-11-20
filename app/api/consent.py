"""Consent endpoints."""

from fastapi import APIRouter

from app.core.deps import CurrentUserDep, SessionDep
from app.schemas.consent import (
    ConsentHistoryResponse,
    ConsentRecord,
    ConsentRequest,
    ConsentStateResponse,
)
from app.services.consent import (
    CONSENT_POLICY_VERSION,
    get_consent_history,
    get_consent_state,
    grant_consent,
)

router = APIRouter(tags=["consent"])


@router.post("/consent", response_model=ConsentStateResponse)
def post_consent(
    user: CurrentUserDep, session: SessionDep, body: ConsentRequest
) -> ConsentStateResponse:
    """Grant or revoke one consent scope.

    Args:
        user: Authenticated user.
        session: Request database session.
        body: Scope and grant flag.

    Returns:
        Current consent state for all scopes.
    """
    grant_consent(session, user, body.scope, body.granted)
    return ConsentStateResponse(
        state=get_consent_state(session, user.id), policy_version=CONSENT_POLICY_VERSION
    )


@router.get("/consent", response_model=ConsentHistoryResponse)
def get_consent(user: CurrentUserDep, session: SessionDep) -> ConsentHistoryResponse:
    """Return the current consent state with full history.

    Args:
        user: Authenticated user.
        session: Request database session.

    Returns:
        State and ledger entries oldest first.
    """
    history = [
        ConsentRecord(
            scope=entry.scope,
            granted=entry.granted,
            policy_version=entry.policy_version,
            created_at=entry.created_at,
        )
        for entry in get_consent_history(session, user.id)
    ]
    return ConsentHistoryResponse(
        state=get_consent_state(session, user.id),
        policy_version=CONSENT_POLICY_VERSION,
        history=history,
    )
