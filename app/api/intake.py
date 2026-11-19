"""Intake endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUserDep, SessionDep, SettingsDep, require_consent
from app.core.enums import ConsentScope
from app.models import User
from app.schemas.intake import (
    IntakeGetResponse,
    IntakeResponse,
    IntakeSchemaDocument,
    IntakeUpdateRequest,
)
from app.services.intake import load_intake, load_intake_schema, save_answers

router = APIRouter(tags=["intake"])

ConsentedUser = Annotated[User, Depends(require_consent(ConsentScope.INTAKE))]


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
    user: ConsentedUser, session: SessionDep, settings: SettingsDep, body: IntakeUpdateRequest
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
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep
) -> IntakeGetResponse:
    """Return the caller's decrypted intake answers.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.

    Returns:
        Stored answers (empty when never saved).
    """
    schema = load_intake_schema(settings.content_dir)
    answers, version, updated_at = load_intake(
        session, user, settings.field_encryption_key, schema
    )
    return IntakeGetResponse(schema_version=version, answers=answers, updated_at=updated_at)
