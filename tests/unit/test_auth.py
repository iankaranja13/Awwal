"""Role account login behaviour."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Role
from app.models import User
from tests.unit.staff_helpers import STAFF_PASSWORD, make_staff


def test_login_returns_token(
    db_client: TestClient, db_session: Session, test_settings: Settings
) -> None:
    """Log in seeded role accounts by handle."""
    make_staff(db_session, test_settings, Role.CLINICIAN)
    handle = db_session.scalar(select(User.pseudonymous_handle))
    assert handle is not None
    response = db_client.post(
        "/api/v1/auth/login", json={"handle": handle, "password": STAFF_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "clinician"
    assert response.json()["token"]


def test_login_rejects_bad_credentials(
    db_client: TestClient, db_session: Session, test_settings: Settings
) -> None:
    """Reject wrong passwords and unknown handles identically."""
    make_staff(db_session, test_settings, Role.NAVIGATOR)
    wrong = db_client.post(
        "/api/v1/auth/login", json={"handle": "user-unknown", "password": "wrong"}
    )
    assert wrong.status_code == 401
    handle = db_session.scalar(select(User.pseudonymous_handle))
    assert handle is not None
    bad = db_client.post("/api/v1/auth/login", json={"handle": handle, "password": "wrong"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_is_rate_limited(db_client: TestClient) -> None:
    """Rate limit login attempts."""
    for _ in range(20):
        db_client.post("/api/v1/auth/login", json={"handle": "nobody", "password": "x"})
    denied = db_client.post("/api/v1/auth/login", json={"handle": "nobody", "password": "x"})
    assert denied.status_code == 429
