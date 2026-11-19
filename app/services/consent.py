"""Consent ledger service (append-only; latest row per scope wins)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.enums import ConsentScope
from app.models import Consent, User
from app.services.audit import record as record_audit

CONSENT_POLICY_VERSION = "v1"


def grant_consent(
    session: Session,
    user: User,
    scope: ConsentScope,
    granted: bool,
    now: datetime | None = None,
) -> Consent:
    """Append one consent grant or revocation and audit it.

    Args:
        session: Database session.
        user: Consenting user.
        scope: Consent scope.
        granted: Whether consent is granted (False revokes).
        now: Timestamp override for deterministic tests.

    Returns:
        The persisted ledger entry (flushed; committed by the caller).
    """
    moment = now if now is not None else utc_now()
    entry = Consent(
        user_id=user.id,
        scope=scope,
        granted=granted,
        policy_version=CONSENT_POLICY_VERSION,
        created_at=moment,
    )
    session.add(entry)
    session.flush()
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="consent.updated",
        object_type="consent",
        object_id=entry.id,
        detail={"scope": scope.value, "granted": granted},
        now=moment,
    )
    return entry


def get_consent_state(session: Session, user_id: UUID) -> dict[ConsentScope, bool]:
    """Derive the current consent state from the ledger.

    Rows sort newest first with the id as a deterministic tiebreak, so the
    same ledger always yields the same state.

    Args:
        session: Database session.
        user_id: User id.

    Returns:
        Granted flag per scope (False when never granted).
    """
    rows = session.scalars(
        select(Consent)
        .where(Consent.user_id == user_id)
        .order_by(Consent.created_at.desc(), Consent.id.desc())
    ).all()
    state = {scope: False for scope in ConsentScope}
    seen: set[ConsentScope] = set()
    for row in rows:
        if row.scope not in seen:
            seen.add(row.scope)
            state[row.scope] = row.granted
    return state


def has_consent(session: Session, user_id: UUID, scope: ConsentScope) -> bool:
    """Check whether one scope is currently granted.

    Args:
        session: Database session.
        user_id: User id.
        scope: Scope to check.

    Returns:
        True when the latest entry for the scope grants consent.
    """
    return get_consent_state(session, user_id)[scope]


def get_consent_history(session: Session, user_id: UUID) -> list[Consent]:
    """List the consent ledger for one user in chronological order.

    Args:
        session: Database session.
        user_id: User id.

    Returns:
        Ledger entries oldest first.
    """
    return list(
        session.scalars(
            select(Consent)
            .where(Consent.user_id == user_id)
            .order_by(Consent.created_at.asc(), Consent.id.asc())
        ).all()
    )
