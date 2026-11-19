"""Explanation and brief endpoint behaviour."""

import json
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import get_llm_client
from app.llm.errors import LLMError
from app.llm.providers.mock import MockProvider
from app.models import Explanation
from tests.unit.rule_helpers import APP_CONTENT_DIR


class _FailingClient:
    """Stub client that always fails."""

    def generate(
        self, system: str, user_json: dict[str, Any], json_schema: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Raise a provider error.

        Args:
            system: Ignored.
            user_json: Ignored.
            json_schema: Ignored.
            timeout: Ignored.

        Raises:
            LLMError: Always.
        """
        raise LLMError("boom")


class _GarbageClient:
    """Stub client returning schema-invalid output."""

    def generate(
        self, system: str, user_json: dict[str, Any], json_schema: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Return an invalid document.

        Args:
            system: Ignored.
            user_json: Ignored.
            json_schema: Ignored.
            timeout: Ignored.

        Returns:
            Invalid mapping.
        """
        return {"nonsense": True}


class _SpyClient:
    """Stub client recording inputs and delegating to the mock."""

    def __init__(self) -> None:
        """Capture generated inputs."""
        self.seen: list[dict[str, Any]] = []
        self.inner = MockProvider(content_dir=str(APP_CONTENT_DIR))

    def generate(
        self, system: str, user_json: dict[str, Any], json_schema: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Record the input and delegate.

        Args:
            system: System prompt text.
            user_json: Structured job input.
            json_schema: Expected schema.
            timeout: Timeout in seconds.

        Returns:
            Mock output.
        """
        self.seen.append(user_json)
        return self.inner.generate(system, user_json, json_schema, timeout)


def _assess_id(db_client: TestClient, headers: dict[str, str], answers: dict[str, Any]) -> str:
    db_client.put("/api/v1/intake", headers=headers, json={"answers": answers})
    return db_client.post("/api/v1/assess", headers=headers).json()["assessment_id"]


def test_explain_uses_llm_by_default(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Regenerate explanations through the mock provider."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    response = db_client.post(
        "/api/v1/explain", headers=consented_headers, json={"assessment_id": assessment_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "llm"
    assert body["used_fallback"] is False
    assert body["model"] == "mock"
    assert body["validator"]["ok"] is True
    assert body["explanation"]["language"] == "en"


def test_explain_regenerates_in_arabic(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Regenerate explanations in the requested language."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    body = db_client.post(
        "/api/v1/explain",
        headers=consented_headers,
        json={"assessment_id": assessment_id, "language": "ar"},
    ).json()
    assert body["language"] == "ar"
    assert body["explanation"]["language"] == "ar"


def test_explain_falls_back_on_provider_error(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Fall back to templates when the provider fails."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    db_client.app.dependency_overrides[get_llm_client] = _FailingClient
    try:
        body = db_client.post(
            "/api/v1/explain", headers=consented_headers, json={"assessment_id": assessment_id}
        ).json()
    finally:
        del db_client.app.dependency_overrides[get_llm_client]
    assert body["source"] == "template"
    assert body["used_fallback"] is True
    assert body["validator"]["ok"] is False


def test_explain_falls_back_on_invalid_output(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Fall back to templates when output fails validation."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    db_client.app.dependency_overrides[get_llm_client] = _GarbageClient
    try:
        body = db_client.post(
            "/api/v1/explain", headers=consented_headers, json={"assessment_id": assessment_id}
        ).json()
    finally:
        del db_client.app.dependency_overrides[get_llm_client]
    assert body["source"] == "template"
    assert body["used_fallback"] is True


def test_explain_urgent_never_calls_llm(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Serve urgent explanations from static content without model calls."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"testicular_pain_sudden_severe": {"value": True, "status": "answered"}},
    )
    spy = _SpyClient()
    db_client.app.dependency_overrides[get_llm_client] = lambda: spy
    try:
        body = db_client.post(
            "/api/v1/explain", headers=consented_headers, json={"assessment_id": assessment_id}
        ).json()
    finally:
        del db_client.app.dependency_overrides[get_llm_client]
    assert body["source"] == "static"
    assert spy.seen == []


def test_explain_hides_other_users_assessments(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Hide other users' assessments from explain."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    other = db_client.post("/api/v1/sessions", json={}).json()["token"]
    response = db_client.post(
        "/api/v1/explain",
        headers={"Authorization": f"Bearer {other}"},
        json={"assessment_id": assessment_id},
    )
    assert response.status_code == 404


def test_llm_input_holds_no_personal_data(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Keep handles and raw values out of LLM inputs."""
    handle = db_client.post("/api/v1/sessions", json={}).json()["handle"]
    token = db_client.post("/api/v1/sessions", json={}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    db_client.post("/api/v1/consent", headers=headers, json={"scope": "intake", "granted": True})
    assessment_id = _assess_id(
        db_client, headers, {"months_trying": {"value": 14, "status": "answered"}}
    )
    spy = _SpyClient()
    db_client.app.dependency_overrides[get_llm_client] = lambda: spy
    try:
        db_client.post(
            "/api/v1/explain", headers=headers, json={"assessment_id": assessment_id}
        )
    finally:
        del db_client.app.dependency_overrides[get_llm_client]
    assert len(spy.seen) == 1
    dumped = json.dumps(spy.seen[0])
    assert handle not in dumped
    assert "14" not in dumped


def test_explain_persists_new_row(
    db_client: TestClient, consented_headers: dict[str, str], db_session: Session
) -> None:
    """Persist regenerated explanations alongside the original."""
    from sqlalchemy import func, select

    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    db_client.post(
        "/api/v1/explain", headers=consented_headers, json={"assessment_id": assessment_id}
    )
    count = db_session.scalar(
        select(func.count()).select_from(Explanation).where(
            Explanation.assessment_id == UUID(assessment_id)
        )
    )
    assert count == 2


def test_brief_serves_owner(db_client: TestClient, consented_headers: dict[str, str]) -> None:
    """Generate a brief for the assessment owner."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    body = db_client.post(
        "/api/v1/brief", headers=consented_headers, json={"assessment_id": assessment_id}
    ).json()
    assert body["source"] == "llm"
    assert body["brief"]["route"] == "PRIMARY_CARE"
    assert body["brief"]["scope_note"]
    assert any(entry["flag_id"] == "MB_DIABETES" for entry in body["brief"]["flags"])


def test_brief_hides_other_users_assessments(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Hide other users' assessments from brief."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    other = db_client.post("/api/v1/sessions", json={}).json()["token"]
    response = db_client.post(
        "/api/v1/brief",
        headers={"Authorization": f"Bearer {other}"},
        json={"assessment_id": assessment_id},
    )
    assert response.status_code == 404


def test_brief_falls_back_on_provider_error(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Fall back to template briefs when the provider fails."""
    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    db_client.app.dependency_overrides[get_llm_client] = _FailingClient
    try:
        body = db_client.post(
            "/api/v1/brief", headers=consented_headers, json={"assessment_id": assessment_id}
        ).json()
    finally:
        del db_client.app.dependency_overrides[get_llm_client]
    assert body["source"] == "template"
    assert body["used_fallback"] is True
    assert body["brief"]["route"] == "PRIMARY_CARE"


def test_brief_audits_generation(
    db_client: TestClient, consented_headers: dict[str, str], db_session: Session
) -> None:
    """Audit brief generations."""
    from sqlalchemy import text

    assessment_id = _assess_id(
        db_client,
        consented_headers,
        {"diabetes": {"value": True, "status": "answered"}},
    )
    db_client.post(
        "/api/v1/brief", headers=consented_headers, json={"assessment_id": assessment_id}
    )
    actions = [
        row[0] for row in db_session.execute(text("SELECT action FROM audit_log")).all()
    ]
    assert "brief.generated" in actions


@pytest.mark.parametrize("endpoint", ["/api/v1/explain", "/api/v1/brief"])
def test_explain_endpoints_require_authentication(db_client: TestClient, endpoint: str) -> None:
    """Reject anonymous explain and brief requests."""
    response = db_client.post(
        endpoint, json={"assessment_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 401
