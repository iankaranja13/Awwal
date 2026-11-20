"""Export, deletion, audit view, privacy copy and dev endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import Role
from app.models import (
    Assessment,
    ClinicianReview,
    Consent,
    Explanation,
    IntakeAnswers,
    Provider,
    Referral,
    User,
    WorkflowTrace,
)
from app.models.base import Base
from tests.unit.rule_helpers import fastapi_app
from tests.unit.staff_helpers import assess_with, make_staff, refer

DIABETES = {"diabetes": {"value": True, "status": "answered"}}


def _count(db_session: Session, model: type[Base]) -> int:
    return db_session.scalar(select(func.count()).select_from(model)) or 0


def test_export_collects_everything(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Export consents, intake, assessments, referrals, shares and audit."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    body = db_client.get("/api/v1/export", headers=consented_headers).json()
    assert body["consents"]
    assert body["intake"]["diabetes"]["value"] is True
    assert len(body["assessments"]) == 1
    assert body["assessments"][0]["explanations"]
    assert len(body["referrals"]) == 1
    assert body["referrals"][0]["events"]
    assert body["shares"] == []
    assert body["audit"]


def test_delete_removes_data_and_marks_user(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Remove personal data, anonymise audit and mark the user."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    review = db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    assert review.status_code == 200, review.text
    summary = db_client.delete("/api/v1/me", headers=consented_headers).json()
    assert summary["removed"]["assessments"] == 1
    assert summary["removed"]["clinician_reviews"] == 1
    assert summary["removed"]["intake_answers"] == 1
    assert summary["removed"]["referrals"] == 1
    assert summary["consents_kept"] >= 1
    assert summary["anonymized_audit_entries"] >= 1
    assert _count(db_session, Assessment) == 0
    assert _count(db_session, ClinicianReview) == 0
    assert _count(db_session, Explanation) == 0
    assert _count(db_session, WorkflowTrace) == 0
    assert _count(db_session, IntakeAnswers) == 0
    assert _count(db_session, Referral) == 0
    assert _count(db_session, Consent) >= 1
    remaining = db_session.execute(text("SELECT COUNT(*) FROM audit_log")).scalar_one()
    assert remaining >= 1
    nulled = db_session.execute(
        text("SELECT COUNT(*) FROM audit_log WHERE actor_id IS NULL")
    ).scalar_one()
    assert nulled >= 1
    user = db_session.scalars(select(User).where(User.role == Role.USER)).one()
    assert user.deleted_at is not None
    assert user.contact_encrypted is None
    assert db_client.get("/api/v1/consent", headers=consented_headers).status_code == 401


def test_audit_view_shows_own_entries(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Show the caller's own audit entries."""
    entries = db_client.get("/api/v1/privacy/audit", headers=consented_headers).json()
    assert entries
    assert all("action" in entry and "at" in entry for entry in entries)


def test_privacy_copy_is_public_and_bilingual(db_client: TestClient) -> None:
    """Serve privacy copy without authentication in both languages."""
    body = db_client.get("/api/v1/content/privacy").json()
    assert body["en"]["title"]
    assert body["ar"]["title"]
    assert len(body["en"]["sections"]) >= 3


def test_seed_is_idempotent(
    db_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seed demo data twice without duplicates."""
    monkeypatch.setenv("SEED_NAVIGATOR_PASSWORD", "navigator-pass")
    monkeypatch.setenv("SEED_CLINICIAN_PASSWORD", "clinician-pass")
    monkeypatch.setenv("SEED_DEMO_USER_PASSWORD", "demo-pass")
    first = db_client.post("/api/v1/dev/seed").json()
    assert first["users"] == 5
    assert first["providers"] == 10
    second = db_client.post("/api/v1/dev/seed").json()
    assert second == {"users": 0, "providers": 0, "consents": 0, "intakes": 0}
    assert _count(db_session, User) == 5


def test_seed_needs_passwords(db_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject seeding without seed passwords."""
    monkeypatch.delenv("SEED_NAVIGATOR_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_CLINICIAN_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_DEMO_USER_PASSWORD", raising=False)
    client = TestClient(db_client.app, raise_server_exceptions=False)
    response = client.post("/api/v1/dev/seed")
    assert response.status_code == 500


def test_reset_drops_users_and_keeps_seeds(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove end users while keeping staff and providers."""
    monkeypatch.setenv("SEED_NAVIGATOR_PASSWORD", "navigator-pass")
    monkeypatch.setenv("SEED_CLINICIAN_PASSWORD", "clinician-pass")
    monkeypatch.setenv("SEED_DEMO_USER_PASSWORD", "demo-pass")
    db_client.post("/api/v1/dev/seed")
    assess_with(db_client, consented_headers, DIABETES)
    removed = db_client.post("/api/v1/dev/reset").json()
    assert removed["users_removed"] >= 4
    assert _count(db_session, Assessment) == 0
    assert _count(db_session, Provider) == 10
    staff = db_session.scalars(select(User)).all()
    assert {user.role.value for user in staff} == {"navigator", "clinician"}


def test_dev_endpoints_hide_when_disabled(db_client: TestClient, test_settings: Settings) -> None:
    """Hide dev endpoints when the admin flag is off."""
    from app.core.database import get_db
    from app.main import create_app

    settings = test_settings.model_copy(update={"enable_dev_admin": False})
    app = create_app(settings)
    app.dependency_overrides[get_db] = fastapi_app(db_client).dependency_overrides[get_db]
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    assert client.post("/api/v1/dev/seed").status_code == 404
    assert client.post("/api/v1/dev/reset").status_code == 404
