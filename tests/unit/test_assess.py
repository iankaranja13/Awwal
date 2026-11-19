"""Assessment endpoint behaviour."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import FlagState, Language, Route
from app.rules_engine.models import FlagResult
from app.rules_engine.models import Label as RuleLabel
from app.schemas.explain import ExplainerOutput
from app.services.content import ExplainerFile, NextStepsFile, SnippetsFile


def _assess(db_client: TestClient, headers: dict[str, str], **params: str) -> dict[str, object]:
    return db_client.post("/api/v1/assess", headers=headers, params=params).json()


def test_assess_requires_consent(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Reject assessments without intake consent."""
    response = db_client.post("/api/v1/assess", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_assess_empty_intake_is_provisional(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Assess users who never saved intake as provisional."""
    response = db_client.post("/api/v1/assess", headers=consented_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["route"] == "SELF_CARE_PROVISIONAL"
    assert body["missing_items"] != []


def test_assess_response_shape(db_client: TestClient, consented_headers: dict[str, str]) -> None:
    """Return the contracted assessment shape."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    response = db_client.post("/api/v1/assess", headers=consented_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["rules_version"] == "0.1"
    assert body["language"] == "en"
    assert body["urgent"] is False
    assert body["route"] == "PRIMARY_CARE"
    assert body["route_reason"] == ["MB_DIABETES"]
    assert body["explanation_source"] == "template"
    assert body["static_safety_message"] is None
    assert "screening" in body["disclaimer"].lower()
    assert body["next_step"]["requires_clinician_review"] is True
    assert body["next_step"]["actions"] == ["book_primary_care"]
    by_id = {flag["id"]: flag for flag in body["flags"]}
    assert by_id["MB_DIABETES"]["state"] == "PRESENT"
    assert by_id["MB_DIABETES"]["explanation"]
    assert by_id["LS_TOBACCO"]["state"] == "NOT_ASSESSABLE"
    assert by_id["LS_TOBACCO"]["missing_fields"] == ["tobacco_vaping_shisha"]
    assert by_id["LS_TOBACCO"]["why_we_ask"]


def test_assess_arabic_labels(db_client: TestClient, consented_headers: dict[str, str]) -> None:
    """Serve flag labels in Arabic when requested."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"diabetes": {"value": True, "status": "answered"}}},
    )
    body = _assess(db_client, consented_headers, lang="ar")
    assert body["language"] == "ar"
    by_id = {flag["id"]: flag for flag in body["flags"]}
    assert by_id["MB_DIABETES"]["label"] == "داء السكري"


def test_assess_language_fallbacks(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Prefer ?lang over the header and fall back to English."""
    headers = dict(consented_headers, **{"Accept-Language": "ar"})
    assert _assess(db_client, headers)["language"] == "ar"
    assert _assess(db_client, headers, lang="en")["language"] == "en"
    assert _assess(db_client, consented_headers, lang="xx")["language"] == "en"


def test_urgent_assessment_is_static(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Short-circuit urgent assessments with static content only."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={
            "answers": {"testicular_pain_sudden_severe": {"value": True, "status": "answered"}}
        },
    )
    body = _assess(db_client, consented_headers)
    assert body["urgent"] is True
    assert body["route"] == "URGENT"
    assert body["flags"] == []
    assert body["explanation_source"] == "static"
    assert body["static_safety_message"]["id"] == "SAFETY_URGENT_PAIN"
    assert body["static_safety_message"]["title"]
    assert body["next_step"]["actions"] == ["seek_urgent_care"]


def test_get_assessment_returns_record(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Rebuild stored assessments on demand."""
    created = _assess(db_client, consented_headers)
    response = db_client.get(
        f"/api/v1/assessments/{created['assessment_id']}", headers=consented_headers
    )
    assert response.status_code == 200
    assert response.json()["assessment_id"] == created["assessment_id"]
    assert response.json()["route"] == created["route"]


def test_get_other_users_assessment_is_hidden(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Hide other users' assessments behind 404."""
    created = _assess(db_client, consented_headers)
    other = db_client.post("/api/v1/sessions", json={}).json()["token"]
    response = db_client.get(
        f"/api/v1/assessments/{created['assessment_id']}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert response.status_code == 404


def test_get_unknown_assessment_is_hidden(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Return 404 for unknown assessments."""
    response = db_client.get(
        "/api/v1/assessments/00000000-0000-0000-0000-000000000000", headers=consented_headers
    )
    assert response.status_code == 404


def test_trace_lists_ordered_steps(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Record every pipeline step with timing."""
    created = _assess(db_client, consented_headers)
    response = db_client.get(f"/api/v1/trace/{created['assessment_id']}", headers=consented_headers)
    assert response.status_code == 200
    body = response.json()
    assert [step["name"] for step in body["steps"]] == [
        "consent_check",
        "load_intake",
        "red_flag_evaluation",
        "flag_evaluation",
        "triage",
        "explanation",
        "persist",
    ]
    assert all(step["status"] == "ok" for step in body["steps"])
    assert all(step["duration_ms"] >= 0 for step in body["steps"])
    assert all(step["rules_version"] == "0.1" for step in body["steps"])
    assert body["duration_ms"] >= 0


def test_urgent_trace_skips_flag_evaluation(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Mark flag evaluation skipped on the urgent path."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={
            "answers": {"testicular_pain_sudden_severe": {"value": True, "status": "answered"}}
        },
    )
    created = _assess(db_client, consented_headers)
    body = db_client.get(
        f"/api/v1/trace/{created['assessment_id']}", headers=consented_headers
    ).json()
    by_name = {step["name"]: step for step in body["steps"]}
    assert by_name["flag_evaluation"]["status"] == "skipped"
    assert by_name["red_flag_evaluation"]["detail"]["present"] == [
        "RF_SUDDEN_SEVERE_TESTICULAR_PAIN"
    ]


def test_template_marks_modifiable_and_unknowns() -> None:
    """Cover template summaries, notes and unknowns directly."""
    from app.llm.templates import build_template_explanation

    present = FlagResult(
        id="LS_TOBACCO",
        state=FlagState.PRESENT,
        domain="lifestyle_exposures",
        label=RuleLabel(en="Tobacco", ar="تبغ"),
        reason_fields=["tobacco_vaping_shisha"],
        modifiable=True,
        suggests_route=Route.PRIMARY_CARE,
        snippet_id="SNP_TOBACCO",
        source="TO BE CONFIRMED",
        requires_clinical_validation=True,
    )
    unknown = FlagResult(
        id="MB_BMI",
        state=FlagState.NOT_ASSESSABLE,
        domain="metabolic",
        label=RuleLabel(en="BMI", ar="مؤشر"),
        missing_fields=["height_cm"],
        modifiable=True,
        suggests_route=Route.PRIMARY_CARE,
        snippet_id="SNP_BMI",
        source="TO BE CONFIRMED",
        requires_clinical_validation=True,
    )
    snippets = SnippetsFile(
        needs_native_review=True, snippets={"SNP_TOBACCO": "Tobacco text.", "SNP_BMI": "BMI text."}
    )
    next_steps = NextStepsFile(
        needs_native_review=True, steps={route.value: f"Next {route.value}" for route in Route}
    )
    explainer = ExplainerFile(
        needs_native_review=True,
        disclaimer="Screening, not a diagnosis.",
        summary_signals="Found {count}.",
        summary_provisional="Incomplete.",
        summary_clear="Clear.",
        modifiable_note="Changeable.",
        brief_scope_owner="Owner view.",
        brief_rationale_prefix="Route from",
        brief_rationale_none="No drivers.",
    )
    output = build_template_explanation(
        Route.PRIMARY_CARE,
        [present, unknown],
        {"height_cm": "Why height."},
        Language.EN,
        snippets,
        next_steps,
        explainer,
    )
    assert isinstance(output, ExplainerOutput)
    assert output.summary == "Found 1."
    by_id = {entry.flag_id: entry for entry in output.flags}
    assert by_id["LS_TOBACCO"].modifiable_note == "Changeable."
    assert by_id["MB_BMI"].unknowns == ["Why height."]


def test_assessment_persists_rows(
    db_client: TestClient, consented_headers: dict[str, str], db_session: Session
) -> None:
    """Persist assessment, explanation and trace rows together."""
    from sqlalchemy import func, select

    from app.models import Assessment, Explanation, WorkflowTrace

    _assess(db_client, consented_headers)
    assert db_session.scalar(select(func.count()).select_from(Assessment)) == 1
    assert db_session.scalar(select(func.count()).select_from(Explanation)) == 1
    assert db_session.scalar(select(func.count()).select_from(WorkflowTrace)) == 1
