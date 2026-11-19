"""Settings validation behaviour."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reject_missing_secrets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fail fast when required secrets are absent."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_invalid_encryption_key() -> None:
    """Fail fast when the encryption key is not a Fernet key."""
    with pytest.raises(ValidationError, match="FIELD_ENCRYPTION_KEY"):
        Settings(jwt_secret="test-secret-value", field_encryption_key="not-a-key")


def test_settings_reject_short_jwt_secret(field_encryption_key: str) -> None:
    """Fail fast when the JWT secret is too short."""
    with pytest.raises(ValidationError):
        Settings(jwt_secret="short", field_encryption_key=field_encryption_key)


def test_settings_split_cors_origins(field_encryption_key: str) -> None:
    """Split comma-separated CORS origins into a clean list."""
    settings = Settings(
        jwt_secret="test-secret-value",
        field_encryption_key=field_encryption_key,
        cors_origins="https://a.example, https://b.example ,,",
    )
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]
