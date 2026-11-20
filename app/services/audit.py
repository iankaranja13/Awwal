"""Audit log service (detail never holds sensitive content)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.enums import Role
from app.models import AuditLog


def record(
    session: Session,
    *,
    actor_id: UUID | None,
    actor_role: Role,
    action: str,
    object_type: str,
    object_id: UUID | None = None,
    detail: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> AuditLog:
    """Append one audit entry.

    Args:
        session: Database session.
        actor_id: Acting user id (None when no user applies).
        actor_role: Acting role.
        action: Action name (for example ``consent.updated``).
        object_type: Affected object type.
        object_id: Affected object id when one applies.
        detail: Small non-sensitive context (ids and names only).
        now: Timestamp override for deterministic tests.

    Returns:
        The persisted entry (flushed; committed by the caller).
    """
    entry = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role.value,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=dict(detail) if detail is not None else {},
        at=now if now is not None else utc_now(),
    )
    session.add(entry)
    session.flush()
    return entry
