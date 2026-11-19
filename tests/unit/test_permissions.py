"""Cross-cutting permission matrix checks."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Role
from app.models import User
from tests.unit.staff_helpers import assess_with, make_staff, refer

DIABETES = {"diabetes": {"value": True, "status": "answered"}}


def test_deleted_users_lose_access(
    db_client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Reject tokens for deleted accounts."""
    user = db_session.scalars(select(User)).one()
    user.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert db_client.get("/api/v1/consent", headers=auth_headers).status_code == 401


def test_staff_cannot_use_user_intake(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Scope intake writes to the caller's own record."""
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    response = db_client.put(
        "/api/v1/intake",
        headers=navigator,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_clinician_reads_referral_metadata(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Allow staff roles to read referral records."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    response = db_client.get(f"/api/v1/referrals/{referral_id}", headers=clinician)
    assert response.status_code == 200
