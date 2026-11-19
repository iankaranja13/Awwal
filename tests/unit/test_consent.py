"""Consent ledger behaviour."""

import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_consent_defaults_all_false(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Report every scope ungranted for new users."""
    response = db_client.get("/api/v1/consent", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == {
        "intake": False,
        "share_with_clinician": False,
        "reminders": False,
        "aggregate_analytics": False,
    }
    assert body["history"] == []


def test_grant_updates_state(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Record grants in the returned state."""
    response = db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "intake", "granted": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["intake"] is True
    assert body["state"]["reminders"] is False
    assert body["policy_version"] == "v1"


def test_revocation_takes_effect_immediately(
    db_client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Apply revocations to the very next read."""
    db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "intake", "granted": True}
    )
    revoked = db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "intake", "granted": False}
    )
    assert revoked.json()["state"]["intake"] is False


def test_scopes_stay_independent(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Keep each scope on its own ledger line."""
    db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "reminders", "granted": True}
    )
    state = db_client.get("/api/v1/consent", headers=auth_headers).json()["state"]
    assert state == {
        "intake": False,
        "share_with_clinician": False,
        "reminders": True,
        "aggregate_analytics": False,
    }


def test_history_lists_entries_oldest_first(
    db_client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Expose the full ledger in chronological order."""
    db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "intake", "granted": True}
    )
    db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "intake", "granted": False}
    )
    history = db_client.get("/api/v1/consent", headers=auth_headers).json()["history"]
    assert [entry["granted"] for entry in history] == [True, False]
    assert history[0]["scope"] == "intake"
    assert history[0]["policy_version"] == "v1"
    stamped = datetime.fromisoformat(history[0]["created_at"].replace("Z", "+00:00"))
    assert stamped.tzinfo is not None


def test_consent_requires_authentication(db_client: TestClient) -> None:
    """Reject anonymous consent reads and writes."""
    assert db_client.get("/api/v1/consent").status_code == 401
    response = db_client.post("/api/v1/consent", json={"scope": "intake", "granted": True})
    assert response.status_code == 401


def test_unknown_scope_rejected(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Reject unknown consent scopes."""
    response = db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "nope", "granted": True}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_grant_writes_audit_entry(
    db_client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Audit consent changes without sensitive content."""
    db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "intake", "granted": True}
    )
    row = db_session.execute(
        text("SELECT action, object_type, actor_role, detail FROM audit_log")
    ).one()
    assert row[0] == "consent.updated"
    assert row[1] == "consent"
    assert row[2] == "user"
    assert json.loads(row[3]) == {"scope": "intake", "granted": True}


def test_stores_scope_values_not_names(
    db_client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Persist lowercase scope values that satisfy the CHECK constraint."""
    db_client.post(
        "/api/v1/consent", headers=auth_headers, json={"scope": "reminders", "granted": True}
    )
    scope = db_session.execute(text("SELECT scope FROM consents")).scalar_one()
    assert scope == "reminders"
