"""Intake schema loading, answer validation and encrypted storage."""

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.crypto import decrypt_json, encrypt_json
from app.core.enums import ItemStatus, ItemType
from app.core.errors import InvalidInputError
from app.models import IntakeAnswers, User
from app.schemas.intake import AnswerIn, IntakeItem, IntakeSchemaDocument
from app.services.audit import record as record_audit

MAX_INTAKE_ITEMS = 200
DEFAULT_TEXT_MAX_LENGTH = 5000


class IntakeSchemaError(Exception):
    """Intake schema file is missing or invalid."""


@lru_cache(maxsize=8)
def load_intake_schema(content_dir: str) -> IntakeSchemaDocument:
    """Load and validate the intake schema document.

    Args:
        content_dir: Directory holding intake_schema.json.

    Returns:
        Validated schema document.

    Raises:
        IntakeSchemaError: If the file is missing or invalid.
    """
    path = Path(content_dir) / "intake_schema.json"
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IntakeSchemaError(f"Cannot read intake schema {path}: {exc.strerror}.") from exc
    except ValueError as exc:
        raise IntakeSchemaError(f"Invalid JSON in {path}: {exc}.") from exc
    try:
        document = IntakeSchemaDocument.model_validate(raw)
    except ValidationError as exc:
        raise IntakeSchemaError(f"Invalid intake schema {path}: {exc}.") from exc
    seen: set[str] = set()
    for item in document.items:
        if item.id in seen:
            raise IntakeSchemaError(f"Duplicate intake item id {item.id}.")
        seen.add(item.id)
        if not item.needs_native_review:
            raise IntakeSchemaError(f"Item {item.id} must keep needs_native_review.")
        if item.type in (ItemType.SINGLE_CHOICE, ItemType.MULTI_CHOICE) and not item.options:
            raise IntakeSchemaError(f"Choice item {item.id} needs options.")
    return document


def _check_value(item: IntakeItem, value: Any) -> str | None:
    """Check one answered value against its item definition.

    Args:
        item: Schema item definition.
        value: Submitted value.

    Returns:
        Reason string when invalid, else None.
    """
    if item.type == ItemType.BOOLEAN:
        return None if type(value) is bool else "needs a boolean value"
    if item.type == ItemType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "needs a numeric value"
        if item.min_value is not None and value < item.min_value:
            return f"needs a value at or above {item.min_value}"
        if item.max_value is not None and value > item.max_value:
            return f"needs a value at or below {item.max_value}"
        return None
    if item.type == ItemType.SINGLE_CHOICE:
        allowed = [option.value for option in item.options]
        return None if value in allowed else f"needs one of {allowed}"
    if item.type == ItemType.MULTI_CHOICE:
        allowed = [option.value for option in item.options]
        if not isinstance(value, list) or not value:
            return "needs a non-empty list of values"
        if any(choice not in allowed for choice in value):
            return f"needs values from {allowed}"
        return None
    cap = item.max_length if item.max_length is not None else DEFAULT_TEXT_MAX_LENGTH
    if not isinstance(value, str):
        return "needs a text value"
    if not value or len(value) > cap:
        return f"needs 1 to {cap} characters"
    return None


def validate_answers(
    schema: IntakeSchemaDocument, answers: dict[str, AnswerIn]
) -> dict[str, dict[str, Any]]:
    """Validate submitted answers and normalise them for storage.

    Args:
        schema: Validated schema document.
        answers: Submitted answers by item id.

    Returns:
        Storage-shape answers (value plus status name per item).

    Raises:
        InvalidInputError: If any answer is unknown, contradictory or mistyped.
    """
    if len(answers) > MAX_INTAKE_ITEMS:
        raise InvalidInputError(
            f"Too many answers (maximum {MAX_INTAKE_ITEMS}).",
            details={"count": len(answers)},
        )
    by_id = {item.id: item for item in schema.items}
    problems: dict[str, str] = {}
    normalised: dict[str, dict[str, Any]] = {}
    for item_id, answer in answers.items():
        item = by_id.get(item_id)
        if item is None:
            problems[item_id] = "unknown item"
            continue
        if answer.status != ItemStatus.ANSWERED and answer.value is not None:
            problems[item_id] = "value must be null unless answered"
            continue
        if answer.status == ItemStatus.ANSWERED and answer.value is None:
            problems[item_id] = "answered needs a value"
            continue
        if answer.status == ItemStatus.ANSWERED:
            reason = _check_value(item, answer.value)
            if reason is not None:
                problems[item_id] = reason
                continue
        normalised[item_id] = {"value": answer.value, "status": answer.status.value}
    if problems:
        raise InvalidInputError("Invalid intake answers.", details={"items": problems})
    return normalised


def get_intake_row(session: Session, user: User) -> IntakeAnswers | None:
    """Load one user's intake row without decrypting.

    Args:
        session: Database session.
        user: Owning user.

    Returns:
        The intake row, or None when never saved.
    """
    return session.scalars(
        select(IntakeAnswers).where(IntakeAnswers.user_id == user.id)
    ).one_or_none()


def get_stored_answers(
    session: Session, user: User, key: str
) -> tuple[dict[str, Any], str | None]:
    """Load and decrypt one user's stored answers.

    Args:
        session: Database session.
        user: Owning user.
        key: Field encryption key.

    Returns:
        Stored answers with the stored schema version (None when never saved).

    Raises:
        CryptoError: If stored data cannot be decrypted.
    """
    row = get_intake_row(session, user)
    if row is None:
        return {}, None
    return decrypt_json(row.answers_encrypted, key), row.schema_version


def load_intake(
    session: Session, user: User, key: str, schema: IntakeSchemaDocument
) -> tuple[dict[str, AnswerIn], str, datetime | None]:
    """Load one user's decrypted intake answers for display.

    Args:
        session: Database session.
        user: Owning user.
        key: Field encryption key.
        schema: Validated schema document (provides the default version).

    Returns:
        Answers with the stored schema version and timestamp.

    Raises:
        CryptoError: If stored data cannot be decrypted.
    """
    row = get_intake_row(session, user)
    if row is None:
        return {}, schema.schema_version, None
    stored = decrypt_json(row.answers_encrypted, key)
    answers = {item_id: AnswerIn.model_validate(entry) for item_id, entry in stored.items()}
    return answers, row.schema_version, row.updated_at


def save_answers(
    session: Session,
    user: User,
    answers: dict[str, AnswerIn],
    schema: IntakeSchemaDocument,
    key: str,
    now: datetime | None = None,
) -> tuple[IntakeAnswers, list[str]]:
    """Validate, merge, encrypt and store intake answers.

    Args:
        session: Database session.
        user: Owning user.
        answers: Submitted answers by item id (partial allowed).
        schema: Validated schema document.
        key: Field encryption key.
        now: Timestamp override for deterministic tests.

    Returns:
        The stored row and the saved item ids.

    Raises:
        InvalidInputError: If any answer is invalid.
        CryptoError: If the encryption key is invalid.
    """
    normalised = validate_answers(schema, answers)
    stored, _ = get_stored_answers(session, user, key)
    stored.update(normalised)
    moment = now if now is not None else utc_now()
    row = session.scalars(
        select(IntakeAnswers).where(IntakeAnswers.user_id == user.id)
    ).one_or_none()
    if row is None:
        row = IntakeAnswers(
            user_id=user.id,
            answers_encrypted=encrypt_json(stored, key),
            schema_version=schema.schema_version,
            updated_at=moment,
        )
        session.add(row)
    else:
        row.answers_encrypted = encrypt_json(stored, key)
        row.schema_version = schema.schema_version
        row.updated_at = moment
    session.flush()
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="intake.updated",
        object_type="intake_answers",
        object_id=row.id,
        detail={"saved_item_ids": sorted(normalised)},
        now=moment,
    )
    return row, sorted(normalised)
