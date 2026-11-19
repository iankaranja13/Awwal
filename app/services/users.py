"""User account service."""

import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Language, Role
from app.core.errors import ConflictError
from app.core.security import create_access_token
from app.models import User

_HANDLE_BYTES = 6
_HANDLE_ATTEMPTS = 3


def generate_handle() -> str:
    """Generate a random pseudonymous handle.

    Returns:
        Handle such as ``user-9f2c4ab71e0d``.
    """
    return f"user-{secrets.token_hex(_HANDLE_BYTES)}"


def get_user(session: Session, user_id: UUID) -> User | None:
    """Load one user by id.

    Args:
        session: Database session.
        user_id: User id.

    Returns:
        The user, or None when unknown.
    """
    return session.get(User, user_id)


def create_anonymous_user(session: Session, language: Language) -> User:
    """Create one anonymous user with a unique handle.

    Args:
        session: Database session.
        language: Preferred interface language.

    Returns:
        The persisted user (flushed; committed by the caller).

    Raises:
        ConflictError: If no unique handle was found after retries.
    """
    for _ in range(_HANDLE_ATTEMPTS):
        try:
            with session.begin_nested():
                user = User(
                    pseudonymous_handle=generate_handle(), role=Role.USER, language=language
                )
                session.add(user)
                session.flush()
        except IntegrityError as exc:
            if "pseudonymous_handle" not in str(exc.orig or exc):
                raise
            continue
        return user
    raise ConflictError("Could not allocate a user handle.")


def create_session(
    session: Session, settings: Settings, language: Language
) -> tuple[User, str]:
    """Create an anonymous user and mint its access token.

    Args:
        session: Database session.
        settings: Application settings.
        language: Preferred interface language.

    Returns:
        The user and its signed access token.
    """
    user = create_anonymous_user(session, language)
    token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        secret=settings.jwt_secret,
        expires_in=timedelta(minutes=settings.jwt_expire_minutes),
    )
    return user, token
