"""Clinician queue and review behaviour."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Role
from tests.unit.staff_helpers import assess_with, make_staff, refer, refer

DIABETES = {"diabetes": {"value": True, "status": "answered"}}


def test_queue_lists_review_state(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """List referrals awaiting review with route context."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral = refer(db_client, consented_headers, assessment_id)
    queue = db_client.get("/api/v1/clinician/queue", headers=clinician).json()
    assert len(queue) == 1
    assert queue[0]["referral_id"] == referral["id"]
    assert queue[0]["route"] == "PRIMARY_CARE"
    assert queue[0]["user_handle"].startswith("user-")
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    assert db_client.get("/api/v1/clinician/queue", headers=clinician).json() == []


def test_queue_rejects_non_clinicians(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Restrict the queue to clinicians."""
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assert db_client.get("/api/v1/clinician/queue", headers=consented_headers).status_code == 403
    assert db_client.get("/api/v1/clinician/queue", headers=navigator).status_code == 403


def test_review_approves_and_signs(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Sign off approvals and confirm the referral."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    body = db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={
            "assessment_id": assessment_id,
            "decision": "approved",
            "edits": {"note": "confirmed"},
            "notes": "Looks routine.",
        },
    ).json()
    assert body["decision"] == "approved"
    assert body["signed_off_at"] is not None
    assert body["referral_status"] == "confirmed"
    raw = db_session.execute(text("SELECT notes FROM clinician_reviews")).scalar_one()
    assert "Looks routine." not in raw


def test_review_rejects_and_cancels(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Cancel referrals on rejection without sign-off."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    body = db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "rejected"},
    ).json()
    assert body["signed_off_at"] is None
    assert body["referral_status"] == "cancelled"


def test_review_without_awaiting_referral(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Reject reviews with nothing awaiting review."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    response = db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    assert response.status_code == 404


def test_review_rejects_non_clinicians(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Restrict reviews to clinicians."""
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    for headers in (consented_headers, navigator):
        response = db_client.post(
            "/api/v1/clinician/review",
            headers=headers,
            json={"assessment_id": assessment_id, "decision": "approved"},
        )
        assert response.status_code == 403


def test_review_rejects_bad_decision(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Reject unknown review decisions."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    response = db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "maybe"},
    )
    assert response.status_code == 422
