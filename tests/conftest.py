"""Shared pytest fixtures."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# Importing app.main builds the default app, which requires secrets. Provide
# throwaway values here so collection never depends on ambient environment.
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.database import create_engine_for, create_session_factory, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.rules_engine import RuleSet, load_rules  # noqa: E402
from tests.unit.rule_helpers import REAL_RULES_DIR, fastapi_app  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parents[1]


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


@pytest.fixture()
def db_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    """Create an isolated migrated SQLite database per test."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        config = Config()
        config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()
    return create_session_factory(create_engine_for(db_url))


@pytest.fixture()
def db_client(client: TestClient, db_factory: sessionmaker[Session]) -> TestClient:
    """Return a test client with database access to the isolated DB."""

    def _override() -> Iterator[Session]:
        session = db_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    fastapi_app(client).dependency_overrides[get_db] = _override
    return client


@pytest.fixture()
def db_session(db_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a direct session to the isolated DB (for raw assertions)."""
    session = db_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture()
def auth_headers(db_client: TestClient) -> dict[str, str]:
    """Create one user and return its auth headers."""
    token = db_client.post("/api/v1/sessions", json={}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def consented_headers(db_client: TestClient, auth_headers: dict[str, str]) -> dict[str, str]:
    """Grant intake consent for the fixture user."""
    db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "intake", "granted": True}
    )
    return auth_headers
