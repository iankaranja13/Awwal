"""Session creation and authentication behaviour."""

from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.models import User


def test_creates_anonymous_session(db_client: TestClient) -> None:
    """Create a pseudonymous user and return its token."""
    response = db_client.post("/api/v1/sessions", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["handle"].startswith("user-")
    assert body["role"] == "user"
    assert body["user_id"]
    assert body["token"]


def test_token_authenticates_requests(db_client: TestClient) -> None:
    """Accept the issued token on authenticated endpoints."""
    token = db_client.post("/api/v1/sessions", json={}).json()["token"]
    response = db_client.get("/api/v1/consent", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_missing_credentials_rejected(db_client: TestClient) -> None:
    """Reject requests without credentials."""
    response = db_client.get("/api/v1/consent")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_tampered_token_rejected(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Reject modified tokens."""
    token = auth_headers["Authorization"].split(" ", 1)[1]
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    response = db_client.get("/api/v1/consent", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


def test_unknown_user_token_rejected(db_client: TestClient, test_settings: Settings) -> None:
    """Reject tokens for users that do not exist."""
    token = create_access_token(
        subject=str(uuid4()),
        role="user",
        secret=test_settings.jwt_secret,
        expires_in=timedelta(minutes=30),
    )
    response = db_client.get("/api/v1/consent", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_role_mismatch_token_rejected(db_client: TestClient, test_settings: Settings) -> None:
    """Reject tokens whose role disagrees with the account."""
    created = db_client.post("/api/v1/sessions", json={}).json()
    token = create_access_token(
        subject=created["user_id"],
        role="clinician",
        secret=test_settings.jwt_secret,
        expires_in=timedelta(minutes=30),
    )
    response = db_client.get("/api/v1/consent", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_language_choice_is_stored(db_client: TestClient, db_session: Session) -> None:
    """Store the requested interface language."""
    created = db_client.post("/api/v1/sessions", json={"language": "ar"}).json()
    user = db_session.get(User, UUID(created["user_id"]))
    assert user is not None
    assert user.language.value == "ar"


def test_stores_enum_values_not_names(db_client: TestClient, db_session: Session) -> None:
    """Persist lowercase enum values that satisfy the CHECK constraints."""
    db_client.post("/api/v1/sessions", json={})
    role = db_session.execute(text("SELECT role FROM users")).scalar_one()
    language = db_session.execute(text("SELECT language FROM users")).scalar_one()
    assert role == "user"
    assert language == "en"


def test_rate_limit_blocks_excess_sessions(db_client: TestClient) -> None:
    """Reject session creation past the per-minute limit."""
    for _ in range(20):
        response = db_client.post("/api/v1/sessions", json={})
        assert response.status_code == 201
    denied = db_client.post("/api/v1/sessions", json={})
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "RATE_LIMITED"
