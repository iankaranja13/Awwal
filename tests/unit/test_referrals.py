"""Referral lifecycle behaviour."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import ReferralType, Role
from app.rules_engine import RuleSet
from tests.unit.rule_helpers import clean_answers
from tests.unit.staff_helpers import assess_with, future_iso, make_provider, make_staff, refer

DIABETES = {"diabetes": {"value": True, "status": "answered"}}


def test_create_moves_to_clinician_review(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Create referrals straight into clinician review."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    body = refer(db_client, consented_headers, assessment_id)
    assert body["status"] == "clinician_review"
    assert [(event["from_status"], event["to_status"]) for event in body["events"]] == [
        (None, "proposed"),
        ("proposed", "clinician_review"),
    ]


def test_self_care_needs_no_booking(
    db_client: TestClient, consented_headers: dict[str, str], ruleset: RuleSet
) -> None:
    """Reject referrals for self-care assessments."""
    clean = {
        item_id: {"value": answer.value, "status": answer.status.value}
        for item_id, answer in clean_answers(ruleset).items()
    }
    assessment_id = assess_with(db_client, consented_headers, clean)
    response = db_client.post(
        "/api/v1/referrals",
        headers=consented_headers,
        json={"assessment_id": assessment_id, "type": "teleconsult"},
    )
    assert response.status_code == 422
    assert "no booking" in response.json()["error"]["message"]


def test_urgent_needs_no_booking(db_client: TestClient, consented_headers: dict[str, str]) -> None:
    """Reject referrals for urgent assessments."""
    assessment_id = assess_with(
        db_client,
        consented_headers,
        {"testicular_pain_sudden_severe": {"value": True, "status": "answered"}},
    )
    response = db_client.post(
        "/api/v1/referrals",
        headers=consented_headers,
        json={"assessment_id": assessment_id, "type": "teleconsult"},
    )
    assert response.status_code == 422


def test_duplicate_active_type_rejected(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Reject duplicate active referrals for one assessment and type."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    response = db_client.post(
        "/api/v1/referrals",
        headers=consented_headers,
        json={"assessment_id": assessment_id, "type": "teleconsult"},
    )
    assert response.status_code == 409
    other = db_client.post(
        "/api/v1/referrals",
        headers=consented_headers,
        json={"assessment_id": assessment_id, "type": "blood_test"},
    )
    assert other.status_code == 201


def test_provider_validated(
    db_client: TestClient, consented_headers: dict[str, str], db_session: Session
) -> None:
    """Validate chosen providers exist and match the type."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    provider = make_provider(db_session, type=ReferralType.BLOOD_TEST)
    mismatch = db_client.post(
        "/api/v1/referrals",
        headers=consented_headers,
        json={
            "assessment_id": assessment_id,
            "type": "teleconsult",
            "provider_id": str(provider.id),
        },
    )
    assert mismatch.status_code == 422
    missing = db_client.post(
        "/api/v1/referrals",
        headers=consented_headers,
        json={
            "assessment_id": assessment_id,
            "type": "teleconsult",
            "provider_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert missing.status_code == 404
    match = db_client.post(
        "/api/v1/referrals",
        headers=consented_headers,
        json={
            "assessment_id": assessment_id,
            "type": "blood_test",
            "provider_id": str(provider.id),
        },
    )
    assert match.status_code == 201
    assert match.json()["provider_id"] == str(provider.id)


def test_contact_stored_encrypted(
    db_client: TestClient, consented_headers: dict[str, str], db_session: Session
) -> None:
    """Store booking contact details encrypted on the user."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(
        db_client,
        consented_headers,
        assessment_id,
        contact={"name": "Sam Example", "phone": "+971500123456"},
    )
    raw = db_session.execute(text("SELECT contact_encrypted FROM users")).scalar_one()
    assert "Sam Example" not in raw
    assert "971500123456" not in raw


def test_full_journey_to_closed(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Walk one referral from review to documented outcome."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    review = db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    assert review.json()["referral_status"] == "confirmed"
    booked = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=consented_headers,
        json={"to_status": "booked", "appointment_time": future_iso()},
    )
    assert booked.json()["status"] == "booked"
    attended = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "attended"},
    )
    assert attended.json()["status"] == "attended"
    explained = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "result_explained"},
    )
    assert explained.json()["status"] == "result_explained"
    closed = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "closed", "outcome_note": "Reviewed, routine follow-up."},
    )
    assert closed.json()["status"] == "closed"
    assert closed.json()["outcome_note"] == "Reviewed, routine follow-up."
    fetched = db_client.get(f"/api/v1/referrals/{referral_id}", headers=consented_headers).json()
    assert len(fetched["events"]) == 7


def test_confirm_requires_sign_off(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Block confirmation without a signed review."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    response = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "confirmed"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


def test_booking_needs_future_aware_time(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Require a future timezone-aware appointment time."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    for body in (
        {"to_status": "booked"},
        {"to_status": "booked", "appointment_time": "2020-01-01T00:00:00+00:00"},
        {"to_status": "booked", "appointment_time": "2030-01-01T00:00:00"},
    ):
        response = db_client.patch(
            f"/api/v1/referrals/{referral_id}/status", headers=consented_headers, json=body
        )
        assert response.status_code == 422, body


def test_closing_needs_outcome_note(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Require an outcome note when closing."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "booked", "appointment_time": future_iso()},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "attended"},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "result_explained"},
    )
    response = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "closed"},
    )
    assert response.status_code == 422


def test_invalid_transitions_rejected(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Reject jumps outside the transition table."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    jump = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "attended"},
    )
    assert jump.status_code == 409
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "rejected"},
    )
    cancelled = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "booked", "appointment_time": future_iso()},
    )
    assert cancelled.status_code == 409


def test_role_gates_enforced(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Reject transitions from unauthorised roles."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    user_confirm = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=consented_headers,
        json={"to_status": "confirmed"},
    )
    assert user_confirm.status_code == 403
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    clinician_book = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician,
        json={"to_status": "booked", "appointment_time": future_iso()},
    )
    assert clinician_book.status_code == 403
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "booked", "appointment_time": future_iso()},
    )
    user_attend = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=consented_headers,
        json={"to_status": "attended"},
    )
    assert user_attend.status_code == 403


def test_other_users_referrals_hidden(
    db_client: TestClient, consented_headers: dict[str, str]
) -> None:
    """Hide other users' referrals behind 404."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    other = db_client.post("/api/v1/sessions", json={}).json()["token"]
    headers = {"Authorization": f"Bearer {other}"}
    assert db_client.get(f"/api/v1/referrals/{referral_id}", headers=headers).status_code == 404
    response = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status", headers=headers, json={"to_status": "cancelled"}
    )
    assert response.status_code == 404


def test_list_scoping(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Scope lists to owners for users and to all for staff."""
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assert len(db_client.get("/api/v1/referrals", headers=consented_headers).json()) == 1
    assert len(db_client.get("/api/v1/referrals", headers=navigator).json()) == 1
    other = db_client.post("/api/v1/sessions", json={}).json()["token"]
    headers = {"Authorization": f"Bearer {other}"}
    assert db_client.get("/api/v1/referrals", headers=headers).json() == []


def test_booking_creates_reminders_with_consent(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Create booking reminders only with reminders consent."""
    from sqlalchemy import func, select

    from app.models import Reminder

    db_client.post(
        "/api/v1/consent",
        headers=consented_headers,
        json={"scope": "reminders", "granted": True},
    )
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=consented_headers,
        json={"to_status": "booked", "appointment_time": future_iso(3)},
    )
    kinds = db_session.scalars(select(Reminder.kind)).all()
    assert sorted(kinds) == ["booking_confirmation", "pre_visit"]


def test_booking_skips_reminders_without_consent(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Skip reminders without reminders consent."""
    from sqlalchemy import func, select

    from app.models import Reminder

    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=consented_headers,
        json={"to_status": "booked", "appointment_time": future_iso(3)},
    )
    count = db_session.scalar(select(func.count()).select_from(Reminder))
    assert count == 0


def test_attended_creates_follow_up(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Create a follow-up reminder after attendance."""
    from sqlalchemy import select

    from app.models import Reminder

    db_client.post(
        "/api/v1/consent",
        headers=consented_headers,
        json={"scope": "reminders", "granted": True},
    )
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "booked", "appointment_time": future_iso(3)},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "attended"},
    )
    kinds = db_session.scalars(select(Reminder.kind)).all()
    assert "follow_up" in kinds


def test_no_show_and_rebook(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Record no-shows and allow navigator rebooking."""
    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    navigator = make_staff(db_session, test_settings, Role.NAVIGATOR)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    referral_id = refer(db_client, consented_headers, assessment_id)["id"]
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "booked", "appointment_time": future_iso(3)},
    )
    missed = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "no_show"},
    )
    assert missed.json()["status"] == "no_show"
    rebooked = db_client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator,
        json={"to_status": "booked", "appointment_time": future_iso(5)},
    )
    assert rebooked.json()["status"] == "booked"


def test_transitions_audited(
    db_client: TestClient,
    consented_headers: dict[str, str],
    db_session: Session,
    test_settings: Settings,
) -> None:
    """Audit referral creation and transitions."""
    from sqlalchemy import text

    clinician = make_staff(db_session, test_settings, Role.CLINICIAN)
    assessment_id = assess_with(db_client, consented_headers, DIABETES)
    refer(db_client, consented_headers, assessment_id)
    db_client.post(
        "/api/v1/clinician/review",
        headers=clinician,
        json={"assessment_id": assessment_id, "decision": "approved"},
    )
    actions = [
        row[0]
        for row in db_session.execute(
            text("SELECT action FROM audit_log WHERE object_type = 'referral'")
        ).all()
    ]
    assert "referral.created" in actions
    assert "referral.transition" in actions
