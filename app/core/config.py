"""Runtime configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values come from environment variables (or a local ``.env`` file).
    Secrets default to empty and are rejected by validators, so
    misconfiguration still fails fast at startup.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", description="Deployment environment name.")
    database_url: str = Field(
        default="postgresql+psycopg://awwal:awwal@db:5432/awwal",
        description="SQLAlchemy database URL.",
    )
    jwt_secret: str = Field(
        default="", min_length=8, description="Secret key for signing JWT access tokens."
    )
    jwt_expire_minutes: int = Field(
        default=120, gt=0, description="Access-token lifetime in minutes."
    )
    field_encryption_key: str = Field(
        default="", description="Fernet key for application-level field encryption."
    )
    cors_origins: str = Field(
        default="http://localhost:3000", description="Comma-separated allowed CORS origins."
    )
    rules_dir: str = Field(default="./rules", description="Directory holding versioned rule files.")
    content_dir: str = Field(
        default="./app/content", description="Directory holding bilingual content files."
    )
    llm_provider: Literal["mock", "anthropic", "openai_compatible"] = Field(
        default="mock", description="LLM provider name."
    )
    llm_model: str = Field(default="", description="LLM model name (never hard-coded in code).")
    llm_api_key: str = Field(default="", description="LLM provider API key.")
    llm_base_url: str = Field(default="", description="Base URL for OpenAI-compatible providers.")
    llm_timeout_seconds: float = Field(
        default=8.0, gt=0, description="LLM request timeout in seconds."
    )
    llm_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="LLM sampling temperature."
    )
    llm_max_tokens: int = Field(default=1024, gt=0, description="LLM maximum output tokens.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Root log level."
    )
    enable_dev_admin: bool = Field(
        default=True, description="Enable dev-only reset/seed endpoints."
    )
    rate_limit_per_minute: int = Field(
        default=20, gt=0, description="Rate limit for guarded endpoints."
    )
    rate_limit_window_seconds: float = Field(
        default=60.0, gt=0, description="Rate limit window in seconds."
    )
    rules_version: str = Field(default="0.1", description="Rule version to load.")

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Map driverless postgres schemes to the installed psycopg driver.

        Hosted providers (Neon, Supabase, Heroku) emit ``postgres://`` URLs;
        SQLAlchemy would pair those with psycopg2, which is not installed.
        Explicit drivers and non-postgres URLs pass through unchanged.

        Args:
            value: Raw database URL from the settings sources.

        Returns:
            The URL with a driverless postgres scheme rewritten, else unchanged.
        """
        scheme, separator, rest = value.partition("://")
        if separator and "+" not in scheme and scheme in ("postgres", "postgresql"):
            return f"postgresql+psycopg://{rest}"
        return value

    @field_validator("field_encryption_key")
    @classmethod
    def _validate_encryption_key(cls, value: str) -> str:
        """Reject values that are not usable Fernet keys.

        Args:
            value: Raw key material from the settings sources.

        Returns:
            The unchanged value when it constructs a Fernet instance.

        Raises:
            ValueError: If the value is not a valid Fernet key.
        """
        try:
            Fernet(value.encode("utf-8"))
        except Exception as exc:
            raise ValueError("FIELD_ENCRYPTION_KEY must be a valid Fernet key.") from exc
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """Split the comma-separated CORS origins into a clean list.

        Returns:
            Allowed origins with whitespace removed and empties dropped.
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings.

    Returns:
        The validated settings singleton for this process.
    """
    return Settings()
