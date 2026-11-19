"""Password hashing and JWT access-token helpers."""

from collections.abc import Callable
from datetime import datetime, timedelta

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, Field

from app.core.clock import utc_now
from app.core.errors import AuthError

_JWT_ALGORITHM = "HS256"

# Shared bcrypt context, created once and never mutated afterwards.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    """Decoded access-token claims."""

    model_config = ConfigDict(frozen=True)

    sub: str = Field(description="Token subject (user id).")
    role: str = Field(description="Caller role (user, navigator or clinician).")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt.

    Args:
        password: Plain-text password (never logged or stored).

    Returns:
        The bcrypt hash for storage.
    """
    hashed: str = _pwd_context.hash(password)
    return hashed


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against its stored bcrypt hash.

    Args:
        password: Plain-text candidate password.
        password_hash: Stored bcrypt hash.

    Returns:
        True when the password matches the hash.
    """
    valid: bool = _pwd_context.verify(password, password_hash)
    return valid


def create_access_token(
    *,
    subject: str,
    role: str,
    secret: str,
    expires_in: timedelta,
    now_fn: Callable[[], datetime] = utc_now,
) -> str:
    """Create a signed JWT access token.

    Args:
        subject: Token subject (user id).
        role: Caller role embedded in the token.
        secret: HMAC secret for signing.
        expires_in: Token lifetime.
        now_fn: Clock injection for deterministic tests.

    Returns:
        The encoded JWT.
    """
    now = now_fn()
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(
    *, token: str, secret: str, now_fn: Callable[[], datetime] = utc_now
) -> TokenPayload:
    """Decode and validate a JWT access token.

    Expiry is checked against the injected clock so tests can fix time;
    the library issued-at check is disabled so the injected clock stays
    authoritative (tokens remain short-lived through the expiry check).

    Args:
        token: Encoded JWT.
        secret: HMAC secret for verification.
        now_fn: Clock injection for deterministic tests.

    Returns:
        The validated token claims.

    Raises:
        AuthError: If the token is invalid, expired or missing claims.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_JWT_ALGORITHM],
            options={"verify_exp": False, "verify_iat": False},
        )
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid access token.") from exc
    expires_at = payload.get("exp")
    if not isinstance(expires_at, (int, float)) or now_fn().timestamp() >= float(expires_at):
        raise AuthError("Access token has expired.")
    subject = payload.get("sub")
    role = payload.get("role")
    if not isinstance(subject, str) or not subject or not isinstance(role, str) or not role:
        raise AuthError("Access token is missing required claims.")
    return TokenPayload(sub=subject, role=role)
