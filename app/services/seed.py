"""Demo seed and reset implementation (dev only)."""

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.crypto import encrypt_json
from app.core.database import create_engine_for, create_session_factory
from app.core.enums import ConsentScope, Language, ReferralType, Role
from app.core.security import hash_password
from app.models import IntakeAnswers, Provider, User
from app.schemas.intake import AnswerIn
from app.services.consent import grant_consent
from app.services.intake import load_intake_schema, validate_answers
from app.services.privacy import erase_user_data


class SeedError(Exception):
    """Seeding prerequisites are missing."""


SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


def _read_json(name: str) -> Any:
    """Read one seed file.

    Args:
        name: File name.

    Returns:
        Parsed JSON document.

    Raises:
        SeedError: If the file is missing or malformed.
    """
    path = SEED_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SeedError(f"Cannot read seed file {path}: {exc.strerror}.") from exc
    except ValueError as exc:
        raise SeedError(f"Invalid JSON in {path}: {exc}.") from exc


def _passwords() -> dict[str, str]:
    """Read seed passwords from the environment.

    Returns:
        Passwords by account kind.

    Raises:
        SeedError: If any password variable is missing.
    """
    names = {
        "navigator": "SEED_NAVIGATOR_PASSWORD",
        "clinician": "SEED_CLINICIAN_PASSWORD",
        "demo_user": "SEED_DEMO_USER_PASSWORD",
    }
    missing = [env for env in names.values() if not os.environ.get(env)]
    if missing:
        raise SeedError(f"Set seed passwords: {', '.join(missing)} (see .env.example).")
    return {kind: os.environ[env] for kind, env in names.items()}


def seed_data(session: Session, key: str, content_dir: str) -> dict[str, int]:
    """Seed demo accounts, providers, consents and intakes idempotently.

    Args:
        session: Database session.
        key: Field encryption key.
        content_dir: Content directory for intake validation.

    Returns:
        Created row counts by section.

    Raises:
        SeedError: If passwords or seed files are missing.
    """
    passwords = _passwords()
    created = {"users": 0, "providers": 0, "consents": 0, "intakes": 0}
    users = {entry["handle"]: entry for entry in _read_json("users.json")}
    for handle, entry in users.items():
        if session.scalars(select(User.id).where(User.pseudonymous_handle == handle)).first():
            continue
        role = Role(entry["role"])
        kind = "demo_user" if role == Role.USER else role.value
        user = User(
            pseudonymous_handle=handle,
            role=role,
            language=Language(entry.get("language", "en")),
            password_hash=hash_password(passwords[kind]),
        )
        session.add(user)
        session.flush()
        created["users"] += 1
        for scope_name, granted in entry.get("consents", {}).items():
            grant_consent(session, user, ConsentScope(scope_name), bool(granted))
            created["consents"] += 1
    for entry in _read_json("providers.json"):
        if session.scalars(select(Provider.id).where(Provider.name == entry["name"])).first():
            continue
        session.add(
            Provider(
                name=entry["name"],
                type=ReferralType(entry["type"]),
                languages=list(entry["languages"]),
                clinician_gender=entry["clinician_gender"],
                tele=bool(entry["tele"]),
                home_sampling=bool(entry["home_sampling"]),
                notes=entry.get("notes", ""),
                mock=True,
            )
        )
        created["providers"] += 1
    session.flush()
    schema = load_intake_schema(content_dir)
    for entry in _read_json("prior_results.json"):
        target = session.scalars(
            select(User).where(User.pseudonymous_handle == entry["user_handle"])
        ).one_or_none()
        if target is None:
            continue
        existing = session.scalars(
            select(IntakeAnswers.id).where(IntakeAnswers.user_id == target.id)
        ).first()
        if existing is not None:
            continue
        answers = {
            item_id: AnswerIn.model_validate(answer) for item_id, answer in entry["answers"].items()
        }
        normalised = validate_answers(schema, answers)
        session.add(
            IntakeAnswers(
                user_id=target.id,
                answers_encrypted=encrypt_json(normalised, key),
                schema_version=schema.schema_version,
            )
        )
        created["intakes"] += 1
    session.flush()
    return created


def reset_demo_data(session: Session) -> dict[str, int]:
    """Hard-delete every end-user account with its data.

    Staff accounts and providers are kept; run the seed afterwards for a
    clean demo.

    Args:
        session: Database session.

    Returns:
        Removed user count.
    """
    users = session.scalars(select(User).where(User.role == Role.USER)).all()
    for user in users:
        erase_user_data(session, user, hard=True)
    session.flush()
    return {"users_removed": len(users)}


def _standalone_session(settings: Settings) -> Session:
    """Open a standalone session for Makefile-driven commands.

    Args:
        settings: Application settings.

    Returns:
        New database session.
    """
    engine = create_engine_for(settings.database_url)
    return create_session_factory(engine)()


def run_seed() -> dict[str, int]:
    """Seed from the environment (Makefile entry point).

    Returns:
        Created row counts by section.
    """
    settings = get_settings()
    session = _standalone_session(settings)
    try:
        created = seed_data(session, settings.field_encryption_key, settings.content_dir)
        session.commit()
        return created
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_reset() -> dict[str, int]:
    """Reset demo data from the environment (Makefile entry point).

    Returns:
        Removed user count.
    """
    settings = get_settings()
    session = _standalone_session(settings)
    try:
        removed = reset_demo_data(session)
        session.commit()
        return removed
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
