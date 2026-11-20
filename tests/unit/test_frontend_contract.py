"""Frontend/backend contract: the UI's mapped payloads drive the real pipeline.

The golden fixture is generated from the real TypeScript mapper
(lib/mapping.ts); regenerate it after mapping changes (see its _note field).
These tests pin the contract from the backend side: the exact payload the UI
sends must assess, book, review and close without surprises.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import ReferralType, Role
from app.models import User
from tests.unit.staff_helpers import future_iso, make_provider, make_staff

GOLDEN = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "frontend_mapping_golden.json").read_text(
        encoding="utf-8"
    )
)
BACKEND_ANSWERS: dict[str, Any] = GOLDEN["backend_answers"]
REVERSE_MAP: dict[str, str] = GOLDEN["reverse_map"]


def test_golden_fixture_matches_mapper() -> None:
    """The committed fixture must equal fresh mapper output (needs node)."""
    repo = Path(__file__).resolve().parents[2]
    node = shutil.which("node")
    if node is None or not (repo / "node_modules" / ".bin" / "tsc").exists():
        pytest.skip("node_modules absent; backend-only checkout.")
    # Fixed argv (repo script, no user input); shell is never used.
    completed = subprocess.run(  # noqa: S603
        [node, "scripts/regen_frontend_golden.mjs", "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _assess(db_client: TestClient, headers: dict[str, str], lang: str) -> dict[str, Any]:
    """Assess in one language and return the response JSON."""
    response = db_client.post(f"/api/v1/assess?lang={lang}", headers=headers)
    assert response.status_code == 201, response.text
    payload: dict[str, Any] = response.json()
    return payload


def test_mapped_golden_assesses_andrology_in_both_languages(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """The UI's mapped payload must assess identically in English and Arabic."""
    saved = db_client.put(
        "/api/v1/intake", headers=consented_headers, json={"answers": BACKEND_ANSWERS}
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["saved_item_ids"]) == len(BACKEND_ANSWERS)
    en = _assess(db_client, consented_headers, "en")
    ar = _assess(db_client, consented_headers, "ar")
    assert en["route"] == ar["route"] == "ANDROLOGY_UROLOGY"
    assert en["urgent"] is False
    assert all("sources" in flag for flag in en["flags"])
    assert "EXC_HX_UNDESCENDED_TESTIS" in next(
        flag["sources"] for flag in en["flags"] if flag["id"] == "HX_UNDESCENDED_TESTIS"
    )
    states = {flag["id"]: flag["state"] for flag in en["flags"]}
    assert states["HX_UNDESCENDED_TESTIS"] == "PRESENT"
    assert states["LS_TTC_STANDARD"] == "PRESENT"
    assert {flag["id"] for flag in ar["flags"]} == set(states)
    assert en["missing_items"] == []
    assert en["explanation_source"] == "template"
    assert "HX_UNDESCENDED_TESTIS" in en["route_reason"]
    trace = db_client.get(f"/api/v1/trace/{en['assessment_id']}", headers=consented_headers).json()
    assert [step["name"] for step in trace["steps"]] == [
        "consent_check",
        "load_intake",
        "red_flag_evaluation",
        "flag_evaluation",
        "triage",
        "explanation",
        "persist",
    ]


def test_mapped_unknown_item_rejected(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Unknown item ids fail, so the UI mapper must only send known ids."""
    response = db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"nope": {"value": True, "status": "answered"}}},
    )
    assert response.status_code == 422


def test_mapped_urgent_short_circuits(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """A UI 'yes' on sudden pain must short-circuit to static urgent text."""
    db_client.put(
        "/api/v1/intake",
        headers=consented_headers,
        json={"answers": {"testicular_pain_sudden_severe": {"value": True, "status": "answered"}}},
    )
    result = _assess(db_client, consented_headers, "en")
    assert result["urgent"] is True
    assert result["route"] == "URGENT"
    assert result["flags"] == []
    assert result["static_safety_message"]["id"] == "SAFETY_URGENT_PAIN"
    assert result["explanation_source"] == "static"


def test_mapped_provisional_missing_items_all_renderable(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Skipped answers escalate to provisional with UI-renderable missing ids."""
    skipped = {item_id: {"value": None, "status": "skipped"} for item_id in BACKEND_ANSWERS}
    db_client.put("/api/v1/intake", headers=consented_headers, json={"answers": skipped})
    result = _assess(db_client, consented_headers, "en")
    assert result["route"] == "SELF_CARE_PROVISIONAL"
    assert result["missing_items"]
    for missing in result["missing_items"]:
        assert missing["item_id"] in REVERSE_MAP


def test_full_user_journey_through_mapped_payload(
    db_client: TestClient,
    db_session: Session,
    test_settings: Settings,
    auth_headers: dict[str, str],
) -> None:
    """Walk the whole UI journey: consent, assess, book, review, close, delete."""
    for scope in ("intake", "share_with_clinician", "reminders", "aggregate_analytics"):
        granted = db_client.post(
            "/api/v1/consent", headers=auth_headers, json={"scope": scope, "granted": True}
        )
        assert granted.status_code == 200, granted.text
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    clinician_id = db_session.scalars(select(User.id).where(User.role == Role.CLINICIAN)).first()
    lab = make_provider(
        db_session, type=ReferralType.BLOOD_TEST, languages=["ar"], clinician_gender="female"
    )
    clinic = make_provider(db_session)
    saved = db_client.put("/api/v1/intake", headers=auth_headers, json={"answers": BACKEND_ANSWERS})
    assert saved.status_code == 200, saved.text
    en = _assess(db_client, auth_headers, "en")
    ar = _assess(db_client, auth_headers, "ar")
    assert en["route"] == ar["route"] == "ANDROLOGY_UROLOGY"
    trace = db_client.get(f"/api/v1/trace/{en['assessment_id']}", headers=auth_headers)
    assert trace.status_code == 200
    filtered = db_client.get(
        "/api/v1/providers?type=teleconsult&language=ar&clinician_gender=male",
        headers=auth_headers,
    ).json()
    assert [row["id"] for row in filtered] == [str(clinic.id)]
    assert lab.id is not None
    share = db_client.post(
        "/api/v1/shares",
        headers=auth_headers,
        json={
            "recipient_id": str(clinician_id),
            "scope": {"all": True},
            "expires_in_hours": 168,
        },
    )
    assert share.status_code == 201, share.text
    created = db_client.post(
        "/api/v1/referrals",
        headers=auth_headers,
        json={
            "assessment_id": en["assessment_id"],
            "type": "teleconsult",
            "provider_id": str(clinic.id),
            "preferred_time": future_iso(),
            "contact": {"phone": "+971500000000"},
        },
    )
    assert created.status_code == 201, created.text
    referral_id = created.json()["id"]
    assert created.json()["status"] == "clinician_review"
    queue = db_client.get("/api/v1/clinician/queue", headers=clinician).json()
    assert [entry["referral_id"] for entry in queue] == [referral_id]
    review = db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": en["assessment_id"], "decision": "approved", "notes": "OK"},
    )
    assert review.json()["referral_status"] == "confirmed", review.text
    for headers, to_status, extra in (
        (navigator, "booked", {"appointment_time": future_iso()}),
        (navigator, "attended", {}),
        (clinician, "result_explained", {}),
        (clinician, "closed", {"outcome_note": "Reviewed, routine follow-up."}),
    ):
        moved = db_client.patch(
            f"/api/v1/referrals/{referral_id}/status",
            headers=headers,
            json={"to_status": to_status, **extra},
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["status"] == to_status
    fetched = db_client.get(f"/api/v1/referrals/{referral_id}", headers=auth_headers).json()
    assert len(fetched["events"]) == 7
    assert fetched["outcome_note"] == "Reviewed, routine follow-up."
    audit = db_client.get("/api/v1/privacy/audit", headers=auth_headers).json()
    assert {"referral.created", "share.created"} <= {entry["action"] for entry in audit}
    export = db_client.get("/api/v1/export", headers=auth_headers).json()
    assert len(export["assessments"]) == 2
    assert len(export["referrals"]) == 1
    revoked = db_client.delete(f"/api/v1/shares/{share.json()['id']}", headers=auth_headers)
    assert revoked.json()["revoked_at"] is not None
    deleted = db_client.delete("/api/v1/me", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["removed"].get("assessments", 0) == 2
