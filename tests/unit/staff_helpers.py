"""Builders for role and referral tests."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Language, ReferralType, Role
from app.core.security import create_access_token, hash_password
from app.models import Provider, User

STAFF_PASSWORD = "staff-password-1"


def make_staff(db_session: Session, test_settings: Settings, role: Role) -> dict[str, str]:
    """Create one staff user and return its auth headers."""
    user = User(
        pseudonymous_handle=f"{role.value}-{uuid4().hex[:8]}",
        role=role,
        language=Language.EN,
        password_hash=hash_password(STAFF_PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(
        subject=str(user.id),
        role=role.value,
        secret=test_settings.jwt_secret,
        expires_in=timedelta(minutes=test_settings.jwt_expire_minutes),
    )
    return {"Authorization": f"Bearer {token}"}


def make_provider(db_session: Session, **overrides: Any) -> Provider:
    """Create one provider and return it."""
    values: dict[str, Any] = {
        "name": f"Clinic {uuid4().hex[:6]}",
        "type": ReferralType.TELECONSULT,
        "languages": ["en", "ar"],
        "clinician_gender": "male",
        "tele": True,
        "home_sampling": False,
        "notes": "",
        "mock": True,
    }
    values.update(overrides)
    provider = Provider(**values)
    db_session.add(provider)
    db_session.commit()
    return provider


def assess_with(db_client: TestClient, headers: dict[str, str], answers: dict[str, Any]) -> str:
    """Save intake and assess, returning the assessment id."""
    db_client.put("/api/v1/intake", headers=headers, json={"answers": answers})
    created = db_client.post("/api/v1/assess", headers=headers).json()
    assessment_id: str = created["assessment_id"]
    return assessment_id


def refer(
    db_client: TestClient, headers: dict[str, str], assessment_id: str, **overrides: Any
) -> dict[str, Any]:
    """Create one referral and return its JSON."""
    body: dict[str, Any] = {"assessment_id": assessment_id, "type": "teleconsult"}
    body.update(overrides)
    response = db_client.post("/api/v1/referrals", headers=headers, json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def future_iso(days: float = 2.0) -> str:
    """Return an aware future timestamp in ISO format."""
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()
