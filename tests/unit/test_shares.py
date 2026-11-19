"""Share grant lifecycle behaviour."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Role
from app.models import User
from tests.unit.staff_helpers import make_staff


def _clinician_id(db_session: Session, test_settings: Settings) -> str:
    make_staff(db_session, test_settings, Role.CLINICIAN)
    return str(db_session.scalar(select(User.id).where(User.role == Role.CLINICIAN)))


def test_create_and_list_shares(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Grant all-scope shares and list them."""
    db_client.post(
        "/api/v1/consent",
        headers=consented_headers,
        json={"scope": "share_with_clinician", "granted": True},
    )
    recipient = _clinician_id(db_session, test_settings)
    created = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={"recipient_id": recipient, "scope": {"all": True}, "expires_in_hours": 48},
    )
    assert created.status_code == 201
    assert created.json()["recipient_id"] == recipient
    listed = db_client.get("/api/v1/shares", headers=consented_headers).json()
    assert len(listed) == 1
    assert listed[0]["revoked_at"] is None


def test_share_requires_sharing_consent(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Reject share creation without the sharing scope."""
    response = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={
            "recipient_id": "00000000-0000-0000-0000-000000000000",
            "scope": {"all": True},
            "expires_in_hours": 48,
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_share_validates_recipient_and_scope(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Reject unknown recipients, non-clinicians and bad scopes."""
    db_client.post(
        "/api/v1/consent",
        headers=consented_headers,
        json={"scope": "share_with_clinician", "granted": True},
    )
    unknown = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={
            "recipient_id": "00000000-0000-0000-0000-000000000000",
            "scope": {"all": True},
            "expires_in_hours": 48,
        },
    )
    assert unknown.status_code == 404
    make_staff(db_session, test_settings, Role.NAVIGATOR)
    navigator_id = str(db_session.scalar(select(User.id).where(User.role == Role.NAVIGATOR)))
    staff = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={"recipient_id": navigator_id, "scope": {"all": True}, "expires_in_hours": 48},
    )
    assert staff.status_code == 422
    clinician_id = _clinician_id(db_session, test_settings)
    bad_scope = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={"recipient_id": clinician_id, "scope": {}, "expires_in_hours": 48},
    )
    assert bad_scope.status_code == 422
    bad_hours = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={"recipient_id": clinician_id, "scope": {"all": True}, "expires_in_hours": 0},
    )
    assert bad_hours.status_code == 422


def test_revoke_share(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Revoke shares immediately."""
    db_client.post(
        "/api/v1/consent",
        headers=consented_headers,
        json={"scope": "share_with_clinician", "granted": True},
    )
    recipient = _clinician_id(db_session, test_settings)
    share_id = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={"recipient_id": recipient, "scope": {"all": True}, "expires_in_hours": 48},
    ).json()["id"]
    revoked = db_client.delete(f"/api/v1/shares/{share_id}", headers=consented_headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None


def test_revoke_other_users_share_hidden(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Hide other users' shares behind 404."""
    response = db_client.delete(
        "/api/v1/shares/00000000-0000-0000-0000-000000000000", headers=consented_headers
    )
    assert response.status_code == 404
