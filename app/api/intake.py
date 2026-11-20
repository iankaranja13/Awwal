"""Intake endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import ConsentedIntakeUser, CurrentUserDep, SessionDep, SettingsDep
from app.core.enums import Role
from app.core.errors import ForbiddenError, NotFoundError
from app.models import User
from app.schemas.intake import (
    IntakeGetResponse,
    IntakeResponse,
    IntakeSchemaDocument,
    IntakeUpdateRequest,
)
from app.services.audit import record as record_audit
from app.services.intake import load_intake, load_intake_schema, save_answers
from app.services.share import has_active_share
from app.services.users import get_user

router = APIRouter(tags=["intake"])


@router.get("/intake/schema", response_model=IntakeSchemaDocument)
def get_schema(_user: CurrentUserDep, settings: SettingsDep) -> IntakeSchemaDocument:
    """Return the bilingual intake schema.

    Args:
        _user: Authenticated user (unused beyond authentication).
        settings: Application settings.

    Returns:
        Versioned schema document.
    """
    return load_intake_schema(settings.content_dir)


@router.put("/intake", response_model=IntakeResponse)
def put_intake(
    user: ConsentedIntakeUser,
    session: SessionDep,
    settings: SettingsDep,
    body: IntakeUpdateRequest,
) -> IntakeResponse:
    """Save intake answers (partial updates allowed).

    Args:
        user: Authenticated user with intake consent.
        session: Request database session.
        settings: Application settings.
        body: Answers by item id.

    Returns:
        Save receipt with stored ids.
    """
    schema = load_intake_schema(settings.content_dir)
    row, saved = save_answers(session, user, body.answers, schema, settings.field_encryption_key)
    return IntakeResponse(
        schema_version=row.schema_version, saved_item_ids=saved, updated_at=row.updated_at
    )


@router.get("/intake", response_model=IntakeGetResponse)
def get_intake(
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    user_id: Annotated[UUID | None, Query()] = None,
) -> IntakeGetResponse:
    """Return decrypted intake answers for the caller or a shared user.

    Clinicians need an all-scope share to read another user's answers.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.
        user_id: Other user id (defaults to the caller).

    Returns:
        Stored answers (empty when never saved).
    """
    target = _resolve_intake_owner(session, user, user_id)
    schema = load_intake_schema(settings.content_dir)
    answers, version, updated_at = load_intake(
        session, target, settings.field_encryption_key, schema
    )
    return IntakeGetResponse(schema_version=version, answers=answers, updated_at=updated_at)


def _resolve_intake_owner(session: SessionDep, user: CurrentUserDep, user_id: UUID | None) -> User:
    """Resolve the intake owner, enforcing shared access.

    Args:
        session: Request database session.
        user: Authenticated user.
        user_id: Requested other user id, if any.

    Returns:
        Owner whose intake is read.

    Raises:
        NotFoundError: If the user is missing or hidden from the caller.
        ForbiddenError: If a clinician lacks an all-scope share.
    """
    if user_id is None or user_id == user.id:
        return user
    if user.role != Role.CLINICIAN:
        raise NotFoundError("User not found.")
    target = get_user(session, user_id)
    if target is None:
        raise NotFoundError("User not found.")
    if not has_active_share(session, target.id, user.id, None):
        raise ForbiddenError("No active share covers this record.")
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="intake.read",
        object_type="intake_answers",
        object_id=target.id,
    )
    return target
