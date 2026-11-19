"""Shared FastAPI dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import AuthError
from app.core.security import decode_access_token
from app.models import User

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
