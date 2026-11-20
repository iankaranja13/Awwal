"""User erasure on Postgres: FK integrity plus the erasure trigger override."""

import os
import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import create_engine_for, create_session_factory, get_db
from app.core.enums import Language, Role
from app.core.security import create_access_token
from app.main import create_app
from app.models import Assessment, ClinicianReview, Consent, Referral, ReferralEvent, User
from tests.unit.staff_helpers import assess_with, refer

needs_postgres = pytest.mark.skipif(
    "postgresql" not in os.environ.get("DATABASE_URL", ""),
    reason="needs a migrated Postgres database URL in DATABASE_URL",
)

DIABETES = {"diabetes": {"value": True, "status": "answered"}}


@pytest.fixture()
def pg_client(test_settings: Settings) -> TestClient:
    """Return a test client bound to the Postgres database URL."""
    app = create_app(test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    factory = create_session_factory(create_engine_for(os.environ["DATABASE_URL"]))

    def _override() -> Iterator[Session]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _pg_session() -> Session:
    """Open a raw session on the Postgres database URL."""
    engine = create_engine_for(os.environ["DATABASE_URL"])
    return Session(engine)


def _clinician(test_settings: Settings) -> dict[str, str]:
    """Create one clinician and return its auth headers."""
    engine = create_engine_for(os.environ["DATABASE_URL"])
    pg = Session(engine)
    try:
        user = User(
            pseudonymous_handle=f"clinician-{uuid.uuid4().hex[:8]}",
            role=Role.CLINICIAN,
            language=Language.EN,
        )
        pg.add(user)
        pg.commit()
        user_id = str(user.id)
    finally:
        pg.close()
        engine.dispose()
    token = create_access_token(
        subject=user_id,
        role=Role.CLINICIAN.value,
        secret=test_settings.jwt_secret,
        expires_in=timedelta(minutes=test_settings.jwt_expire_minutes),
    )
    return {"Authorization": f"Bearer {token}"}


def _user_headers(pg_client: TestClient) -> dict[str, str]:
    """Create one anonymous user with intake consent."""
    token = pg_client.post("/api/v1/sessions", json={}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    pg_client.post("/api/v1/consent", headers=headers, json={"scope": "intake", "granted": True})
    return headers


@needs_postgres
def test_soft_erase_removes_reviewed_aggregate(
    pg_client: TestClient, test_settings: Settings
) -> None:
    """Erase a reviewed referral aggregate without FK violations."""
    headers = _user_headers(pg_client)
    assessment_id = assess_with(pg_client, headers, DIABETES)
    refer(pg_client, headers, assessment_id)
    clinician = _clinician(test_settings)
    review = pg_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    assert review.status_code == 200, review.text
    summary = pg_client.delete("/api/v1/me", headers=headers).json()
    assert summary["removed"]["assessments"] == 1
    assert summary["removed"]["clinician_reviews"] == 1
    assert summary["removed"]["referrals"] == 1
    assert summary["removed"]["referral_events"] == 3
    assert summary["consents_kept"] >= 1
    assert pg_client.get("/api/v1/consent", headers=headers).status_code == 401


@needs_postgres
def test_hard_reset_removes_consents_with_users(pg_client: TestClient) -> None:
    """Reset end users without leaving consent rows behind."""
    headers = _user_headers(pg_client)
    assess_with(pg_client, headers, DIABETES)
    removed = pg_client.post("/api/v1/dev/reset").json()
    assert removed["users_removed"] >= 1
    pg = _pg_session()
    try:
        leftovers = pg.scalar(select(func.count()).select_from(User).where(User.role == Role.USER))
        assert leftovers == 0
    finally:
        pg.close()


@needs_postgres
def test_referral_events_reject_writes_without_override(pg_client: TestClient) -> None:
    """Block UPDATE and DELETE on referral_events outside erasure."""
    headers = _user_headers(pg_client)
    assessment_id = assess_with(pg_client, headers, DIABETES)
    refer(pg_client, headers, assessment_id)
    pg = _pg_session()
    try:
        event_id = pg.scalars(select(ReferralEvent.id)).first()
        assert event_id is not None
        with pytest.raises(DBAPIError, match="append-only"):
            pg.execute(
                text("UPDATE referral_events SET to_status = 'booked' WHERE id = :id"),
                {"id": event_id},
            )
            pg.flush()
        pg.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            pg.execute(text("DELETE FROM referral_events WHERE id = :id"), {"id": event_id})
            pg.flush()
        pg.rollback()
    finally:
        pg.close()
    summary = pg_client.delete("/api/v1/me", headers=headers).json()
    assert summary["removed"]["referral_events"] == 2
    assert summary["removed"]["referrals"] == 1


def test_models_cover_erase_aggregate() -> None:
    """Reference every erased model so renames break loudly."""
    assert Assessment.__tablename__ == "assessments"
    assert ClinicianReview.__tablename__ == "clinician_reviews"
    assert Consent.__tablename__ == "consents"
    assert Referral.__tablename__ == "referrals"
    assert ReferralEvent.__tablename__ == "referral_events"
