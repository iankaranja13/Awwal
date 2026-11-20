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


def test_settings_normalize_driverless_postgres_url(field_encryption_key: str) -> None:
    """Map hosted postgres:// URLs to the installed psycopg driver."""
    settings = Settings(
        jwt_secret="test-secret-value",
        field_encryption_key=field_encryption_key,
        database_url="postgres://u:p@host:5432/db?sslmode=require",
    )
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db?sslmode=require"


def test_settings_keep_explicit_database_driver(field_encryption_key: str) -> None:
    """Leave explicit drivers and sqlite URLs unchanged."""
    url = "postgresql+psycopg://u:p@host:5432/db"
    settings = Settings(
        jwt_secret="test-secret-value", field_encryption_key=field_encryption_key, database_url=url
    )
    assert settings.database_url == url
    lite = Settings(
        jwt_secret="test-secret-value",
        field_encryption_key=field_encryption_key,
        database_url="sqlite:////tmp/test.db",
    )
    assert lite.database_url == "sqlite:////tmp/test.db"
