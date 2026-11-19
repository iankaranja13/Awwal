"""Password and JWT helper behaviour."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.errors import AuthError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-jwt-secret"
FIXED_NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


def _fixed_now() -> datetime:
    return FIXED_NOW


def _make_token(expires_in: timedelta) -> str:
    return create_access_token(
        subject="user-123",
        role="user",
        secret=SECRET,
        expires_in=expires_in,
        now_fn=_fixed_now,
    )


def test_hash_and_verify_password_round_trip() -> None:
    """Hash then verify the same password."""
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    """Reject a password that does not match the hash."""
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_access_token_round_trip_with_fixed_clock() -> None:
    """Encode then decode a token with deterministic time."""
    token = _make_token(timedelta(minutes=30))
    payload = decode_access_token(token=token, secret=SECRET, now_fn=_fixed_now)
    assert payload.sub == "user-123"
    assert payload.role == "user"


def test_decode_rejects_expired_token() -> None:
    """Reject a token past its expiry."""
    token = _make_token(timedelta(minutes=30))
    late = FIXED_NOW + timedelta(hours=1)
    with pytest.raises(AuthError, match="expired"):
        decode_access_token(token=token, secret=SECRET, now_fn=lambda: late)


def test_decode_rejects_tampered_token() -> None:
    """Reject a token whose signature was modified."""
    token = _make_token(timedelta(minutes=30))
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(AuthError, match="Invalid access token"):
        decode_access_token(token=tampered, secret=SECRET, now_fn=_fixed_now)


def test_decode_rejects_wrong_secret() -> None:
    """Reject a token verified with a different secret."""
    token = _make_token(timedelta(minutes=30))
    with pytest.raises(AuthError, match="Invalid access token"):
        decode_access_token(token=token, secret="another-test-secret", now_fn=_fixed_now)


def test_decode_rejects_missing_claims() -> None:
    """Reject tokens without subject or role claims."""
    payload = {"exp": int((FIXED_NOW + timedelta(minutes=5)).timestamp())}
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(AuthError, match="missing required claims"):
        decode_access_token(token=token, secret=SECRET, now_fn=_fixed_now)
