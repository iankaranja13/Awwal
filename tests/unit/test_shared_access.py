"""Shared-record access for clinicians."""

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Role
from app.models import User
from tests.unit.staff_helpers import assess_with, make_staff

DIABETES = {"diabetes": {"value": True, "status": "answered"}}


def _grant(
    db_client: TestClient,
    headers: dict[str, str],
    recipient: str,
    scope: dict[str, object],
) -> None:
    db_client.post(
        "/api/v1/consent",
        headers=headers,
        json={"scope": "share_with_clinician", "granted": True},
    )
    response = db_client.post(
        "/api/v1/shares",
        headers=headers,
        json={"recipient_id": recipient, "scope": scope, "expires_in_hours": 48},
    )
    assert response.status_code == 201, response.text


def _clinician(
    db_client: TestClient, db_session: Session, test_settings: Settings
) -> tuple[dict[str, str], str]:
    headers = make_staff(db_session, test_settings, Role.CLINICIAN)
    clinician_id = str(db_session.scalar(select(User.id).where(User.role == Role.CLINICIAN)))
    return headers, clinician_id


def test_shared_assessment_read(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Open shared assessments, traces and briefs to clinicians."""
    clinician, clinician_id = _clinician(db_client, db_session, test_settings)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    denied = db_client.get(f"/api/v1/assessments/{assessment_id}", headers=clinician)
    assert denied.status_code == 403
    _grant(db_client, consented_headers, clinician_id, {"all": True})
    fetched = db_client.get(f"/api/v1/assessments/{assessment_id}", headers=clinician)
    assert fetched.status_code == 200
    assert fetched.json()["assessment_id"] == assessment_id
    trace = db_client.get(f"/api/v1/trace/{assessment_id}", headers=clinician)
    assert trace.status_code == 200
    brief = db_client.post(
        "/api/v1/brief", headers=clinician, json={"assessment_id": assessment_id}
    ).json()
    assert "Shared view" in brief["brief"]["scope_note"]


def test_ids_scope_limits_assessments(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Restrict ids-scope shares to listed assessments."""
    clinician, clinician_id = _clinician(db_client, db_session, test_settings)
    first = assess_with(db_client, consented_headers, DIABETES)
    second = assess_with(db_client, consented_headers, DIABETES)
    _grant(db_client, consented_headers, clinician_id, {"assessment_ids": [first]})
    assert db_client.get(f"/api/v1/assessments/{first}", headers=clinician).status_code == 200
    assert db_client.get(f"/api/v1/assessments/{second}", headers=clinician).status_code == 403


def test_revoked_share_closes_access(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Close access immediately on revocation."""
    clinician, clinician_id = _clinician(db_client, db_session, test_settings)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    db_client.post(
        "/api/v1/consent",
        headers=consented_headers,
        json={"scope": "share_with_clinician", "granted": True},
    )
    share_id = db_client.post(
        "/api/v1/shares",
        headers=consented_headers,
        json={"recipient_id": clinician_id, "scope": {"all": True}, "expires_in_hours": 48},
    ).json()["id"]
    shared = db_client.get(f"/api/v1/assessments/{assessment_id}", headers=clinician)
    assert shared.status_code == 200
    db_client.delete(f"/api/v1/shares/{share_id}", headers=consented_headers)
    closed = db_client.get(f"/api/v1/assessments/{assessment_id}", headers=clinician)
    assert closed.status_code == 403


def test_shared_intake_needs_all_scope(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Open whole-record intake only to all-scope shares."""
    clinician, clinician_id = _clinician(db_client, db_session, test_settings)
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": DIABETES},
    )
    owner = db_session.scalar(select(User.id).where(User.role == Role.USER))
    assert owner is not None
    denied = db_client.get(f"/api/v1/intake?user_id={owner}", headers=clinician)
    assert denied.status_code == 403
    _grant(db_client, consented_headers, clinician_id, {"all": True})
    fetched = db_client.get(f"/api/v1/intake?user_id={owner}", headers=clinician).json()
    assert fetched["answers"]["diabetes"]["value"] is True


def test_clinician_reads_audited(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Log every clinician read of shared records."""
    clinician, clinician_id = _clinician(db_client, db_session, test_settings)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    _grant(db_client, consented_headers, clinician_id, {"all": True})
    db_client.get(f"/api/v1/assessments/{assessment_id}", headers=clinician)
    actions = [row[0] for row in db_session.execute(text("SELECT action FROM audit_log")).all()]
    assert "assessment.read" in actions
    owner_view = db_client.get("/api/v1/privacy/audit", headers=consented_headers).json()
    reads = [entry for entry in owner_view if entry["action"] == "assessment.read"]
    assert len(reads) == 1
    assert reads[0]["actor_role"] == "clinician"


def test_navigator_cannot_use_shares(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Deny shared assessment access to navigators."""
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    response = db_client.get(f"/api/v1/assessments/{assessment_id}", headers=navigator)
    assert response.status_code == 404
