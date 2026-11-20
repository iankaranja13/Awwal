"""Intake storage and validation behaviour."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_put_requires_intake_consent(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Reject intake writes without the intake scope."""
    response = db_client.put(
        "/api/v1/intake",
        headers=auth_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "CONSENT_REQUIRED"
    assert body["details"] == {"scope": "intake"}


def test_put_and_get_round_trip(db_client: TestClient, consented_headers: dict[str, str]) -> None:
    """Store and return decrypted answers."""
    saved = db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    assert saved.status_code == 200
    assert saved.json()["saved_item_ids"] == ["diabetes"]
    assert saved.json()["schema_version"] == "0.1"
    fetched = db_client.get("/api/v1/intake", headers=consented_headers)
    assert fetched.json()["answers"] == {"diabetes": {"value": True, "status": "answered"}}


def test_put_merges_partial_updates(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Merge partial updates with previously stored answers."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"height_cm": {"value": 178, "status": "answered"}}},
    )
    answers = db_client.get("/api/v1/intake", headers=consented_headers).json()["answers"]
    assert set(answers) == {"diabetes", "height_cm"}


def test_put_overwrites_items(db_client: TestClient, consented_headers: dict[str, str]) -> None:
    """Overwrite resubmitted items."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": False, "status": "answered"}}},
    )
    answers = db_client.get("/api/v1/intake", headers=consented_headers).json()["answers"]
    assert answers["diabetes"] == {"value": False, "status": "answered"}


def test_get_empty_intake(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Return empty answers when nothing was saved."""
    response = db_client.get("/api/v1/intake", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["answers"] == {}
    assert response.json()["updated_at"] is None


def test_intake_requires_authentication(db_client: TestClient) -> None:
    """Reject anonymous intake reads and writes."""
    assert db_client.get("/api/v1/intake").status_code == 401
    response = db_client.put("/api/v1/intake", json={"answers": {}})
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("item_id", "answer"),
    [
        ("no_such_item", {"value": True, "status": "answered"}),
        ("diabetes", {"value": 1, "status": "answered"}),
        ("height_cm", {"value": "tall", "status": "answered"}),
        ("height_cm", {"value": 400, "status": "answered"}),
        ("height_cm", {"value": 20, "status": "answered"}),
        ("tobacco_vaping_shisha", {"value": "sometimes", "status": "answered"}),
        ("diabetes", {"value": None, "status": "answered"}),
        ("diabetes", {"value": True, "status": "skipped"}),
        ("regular_medications_text", {"value": "x" * 2001, "status": "answered"}),
        ("regular_medications_text", {"value": 42, "status": "answered"}),
    ],
)
def test_invalid_answers_rejected(
    db_client: TestClient,
    consented_headers: dict[str, str],
    item_id: str,
    answer: dict[str, object],
) -> None:
    """Reject mistyped, contradictory or unknown answers."""
    response = db_client.put(
        "/api/v1/intake", headers=consented_headers, json={"answers": {item_id: answer}}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_oversized_payload_rejected(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Reject answer payloads past the size bound."""
    answers = {f"item_{index}": {"value": True, "status": "answered"} for index in range(201)}
    response = db_client.put("/api/v1/intake", headers=consented_headers, json={"answers": answers})
    assert response.status_code == 422
    assert "Too many" in response.json()["error"]["message"]


def test_answers_stored_encrypted(
    db_client: TestClient, consented_headers: dict[str, str], db_session: Session
) -> None:
    """Store answers as ciphertext, never plaintext."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    raw = db_session.execute(text("SELECT answers_encrypted FROM intake_answers")).scalar_one()
    assert "diabetes" not in raw
    assert "True" not in raw


def test_save_writes_audit_entry(
    db_client: TestClient, consented_headers: dict[str, str], db_session: Session
) -> None:
    """Audit intake writes with saved ids only."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    row = db_session.execute(
        text("SELECT action, object_type, detail FROM audit_log WHERE action = 'intake.updated'")
    ).one()
    assert row[0] == "intake.updated"
    assert row[1] == "intake_answers"
    assert json.loads(row[2]) == {"saved_item_ids": ["diabetes"]}
