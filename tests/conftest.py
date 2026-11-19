"""Shared pytest fixtures."""

import os

import pytest
from cryptography.fernet import Fernet

# Importing app.main builds the default app, which requires secrets. Provide
# throwaway values here so collection never depends on ambient environment.
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.rules_engine import RuleSet, load_rules  # noqa: E402
from tests.unit.rule_helpers import REAL_RULES_DIR  # noqa: E402


@pytest.fixture()
def field_encryption_key() -> str:
    """Generate a fresh Fernet key for tests."""
    return Fernet.generate_key().decode("utf-8")


@pytest.fixture()
def test_settings(field_encryption_key: str) -> Settings:
    """Build isolated settings for tests (no environment needed)."""
    return Settings(
        app_env="test",
        jwt_secret="test-secret-for-unit-tests",
        field_encryption_key=field_encryption_key,
    )


@pytest.fixture()
def client(test_settings: Settings) -> TestClient:
    """Return a test client bound to isolated settings."""
    app = create_app(test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)


@pytest.fixture(scope="session")
def ruleset() -> RuleSet:
    """Load the real v0.1 rule set once per session."""
    return load_rules(REAL_RULES_DIR, "0.1")
