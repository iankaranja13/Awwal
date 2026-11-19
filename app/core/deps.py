"""Shared FastAPI dependencies."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.enums import ConsentScope, Language
from app.core.errors import AuthError, ConsentRequiredError
from app.core.security import decode_access_token
from app.llm.client import LLMClient, create_client
from app.models import User
from app.services.consent import has_consent

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    """Authenticate the caller from a bearer token.

    Args:
        credentials: Bearer credentials from the Authorization header.
        session: Request database session.
        settings: Application settings.

    Returns:
        Authenticated user.

    Raises:
        AuthError: If credentials are missing, invalid or stale.
    """
    if credentials is None:
        raise AuthError("Missing bearer credentials.")
    payload = decode_access_token(token=credentials.credentials, secret=settings.jwt_secret)
    try:
        user_id = UUID(payload.sub)
    except ValueError as exc:
        raise AuthError("Invalid token subject.") from exc
    user = session.get(User, user_id)
    if user is None:
        raise AuthError("Unknown user.")
    if user.deleted_at is not None:
        raise AuthError("Account is deleted.")
    if user.role.value != payload.role:
        raise AuthError("Token role does not match the account.")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_consent(scope: ConsentScope) -> Callable[[User, Session], User]:
    """Build a dependency enforcing one consent scope.

    Args:
        scope: Required consent scope.

    Returns:
        Dependency returning the user when consent holds.
    """

    def _check_consent(user: CurrentUserDep, session: SessionDep) -> User:
        """Enforce the consent scope for the current user.

        Args:
            user: Authenticated user.
            session: Request database session.

        Returns:
            The user when consent holds.

        Raises:
            ConsentRequiredError: When the scope was not granted.
        """
        if not has_consent(session, user.id, scope):
            raise ConsentRequiredError(details={"scope": scope.value})
        return user

    return _check_consent


ConsentedIntakeUser = Annotated[User, Depends(require_consent(ConsentScope.INTAKE))]


def get_language(
    lang: Annotated[str | None, Query()] = None,
    accept_language: Annotated[str | None, Header()] = None,
) -> Language:
    """Resolve the response language from query or header.

    Explicit ?lang wins; otherwise the Accept-Language prefix applies;
    anything unknown falls back to English.

    Args:
        lang: Optional explicit language query value.
        accept_language: Optional Accept-Language header value.

    Returns:
        Resolved language.
    """
    if lang is not None:
        normalized = lang.strip().lower()
        if normalized.startswith("ar"):
            return Language.AR
        return Language.EN
    if accept_language is not None:
        first = accept_language.split(",")[0].strip().lower()
        if first.startswith("ar"):
            return Language.AR
    return Language.EN


LanguageDep = Annotated[Language, Depends(get_language)]


def get_llm_client(settings: SettingsDep) -> LLMClient:
    """Create the configured LLM client.

    Args:
        settings: Application settings.

    Returns:
        Provider client.
    """
    return create_client(settings)


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
