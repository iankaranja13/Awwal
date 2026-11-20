"""Export and erasure service for user data."""

from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.core.clock import utc_now
from app.models import (
    Assessment,
    AuditLog,
    ClinicianReview,
    Consent,
    Explanation,
    IntakeAnswers,
    Referral,
    ReferralEvent,
    Reminder,
    Share,
    User,
    WorkflowTrace,
)
from app.models.base import Base
from app.schemas.intake import AnswerIn
from app.schemas.privacy import AuditEntryOut, DeleteResponse, ExportResponse
from app.services.consent import get_consent_history
from app.services.intake import get_stored_answers

ModelT = TypeVar("ModelT", bound=Base)


def _audit_entries(session: Session, user_id: UUID) -> list[AuditEntryOut]:
    """List one user's audit entries: own actions plus accesses to their data.

    Args:
        session: Database session.
        user_id: Owning user id.

    Returns:
        Audit entries newest first.
    """
    own_assessments = select(Assessment.id).where(Assessment.user_id == user_id)
    rows = session.scalars(
        select(AuditLog)
        .where(
            (AuditLog.actor_id == user_id)
            | ((AuditLog.object_type == "assessment") & (AuditLog.object_id.in_(own_assessments)))
            | ((AuditLog.object_type == "intake_answers") & (AuditLog.object_id == user_id))
        )
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
    ).all()
    return [
        AuditEntryOut(
            id=row.id,
            actor_role=row.actor_role,
            action=row.action,
            object_type=row.object_type,
            object_id=row.object_id,
            at=row.at,
            detail=dict(row.detail),
        )
        for row in rows
    ]


def own_audit(session: Session, user: User) -> list[AuditEntryOut]:
    """List the caller's own audit entries.

    Args:
        session: Database session.
        user: Authenticated user.

    Returns:
        Audit entries newest first.
    """
    return _audit_entries(session, user.id)


def build_export(session: Session, user: User, key: str) -> ExportResponse:
    """Build a full export of one user's data.

    Args:
        session: Database session.
        user: Exporting user.
        key: Field encryption key.

    Returns:
        Complete export document.
    """
    consents = [
        {
            "scope": entry.scope.value,
            "granted": entry.granted,
            "policy_version": entry.policy_version,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in get_consent_history(session, user.id)
    ]
    stored, _ = get_stored_answers(session, user, key)
    intake = {
        item_id: AnswerIn.model_validate(entry).model_dump(mode="json")
        for item_id, entry in stored.items()
    }
    assessments: list[dict[str, Any]] = []
    assessment_rows = session.scalars(select(Assessment).where(Assessment.user_id == user.id)).all()
    for assessment_row in assessment_rows:
        explanations = session.scalars(
            select(Explanation).where(Explanation.assessment_id == assessment_row.id)
        ).all()
        assessments.append(
            {
                "id": str(assessment_row.id),
                "rules_version": assessment_row.rules_version,
                "route": assessment_row.route.value,
                "urgent": assessment_row.urgent,
                "route_reason": list(assessment_row.route_reason),
                "flags": list(assessment_row.flags),
                "missing_items": list(assessment_row.missing_items),
                "created_at": assessment_row.created_at.isoformat(),
                "explanations": [
                    {
                        "language": item.language.value,
                        "source": item.source.value,
                        "model": item.model,
                        "prompt_version": item.prompt_version,
                        "text": dict(item.text),
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in explanations
                ],
            }
        )
    referrals: list[dict[str, Any]] = []
    referral_rows = session.scalars(select(Referral).where(Referral.user_id == user.id)).all()
    for referral_row in referral_rows:
        events = session.scalars(
            select(ReferralEvent).where(ReferralEvent.referral_id == referral_row.id)
        ).all()
        referrals.append(
            {
                "id": str(referral_row.id),
                "assessment_id": str(referral_row.assessment_id),
                "type": referral_row.type.value,
                "status": referral_row.status.value,
                "provider_id": str(referral_row.provider_id) if referral_row.provider_id else None,
                "events": [
                    {
                        "from_status": event.from_status.value if event.from_status else None,
                        "to_status": event.to_status.value,
                        "at": event.at.isoformat(),
                    }
                    for event in events
                ],
            }
        )
    reminders = [
        {
            "referral_id": str(row.referral_id),
            "kind": row.kind,
            "due_at": row.due_at.isoformat(),
            "simulated_sent_at": row.simulated_sent_at.isoformat()
            if row.simulated_sent_at
            else None,
        }
        for row in session.scalars(
            select(Reminder).where(
                Reminder.referral_id.in_(select(Referral.id).where(Referral.user_id == user.id))
            )
        ).all()
    ]
    shares = [
        {
            "recipient_id": str(row.recipient_id),
            "scope": dict(row.scope),
            "expires_at": row.expires_at.isoformat(),
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        }
        for row in session.scalars(select(Share).where(Share.user_id == user.id)).all()
    ]
    return ExportResponse(
        consents=consents,
        intake=intake,
        assessments=assessments,
        referrals=referrals,
        reminders=reminders,
        shares=shares,
        audit=_audit_entries(session, user.id),
    )


def erase_user_data(
    session: Session, user: User, hard: bool, now: datetime | None = None
) -> DeleteResponse:
    """Erase one user's data with audit anonymisation.

    Consent receipts stay as the legal record on self-delete; a hard
    reset removes them with the row they reference. Referral events go
    with their referrals (erasure sets a transaction-local override the
    trigger honours); audit rows are anonymised, never deleted.

    Args:
        session: Database session.
        user: User being erased.
        hard: Whether to delete the user row (reset) or mark it (self-delete).
        now: Timestamp override for deterministic tests.

    Returns:
        Deletion summary.
    """
    moment = now if now is not None else utc_now()
    removed: dict[str, int] = {}
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(text("SET LOCAL awwal.erase_override = 'on'"))
    assessment_ids = session.scalars(
        select(Assessment.id).where(Assessment.user_id == user.id)
    ).all()
    referral_ids = session.scalars(select(Referral.id).where(Referral.user_id == user.id)).all()
    removed["reminders"] = _delete_where(session, Reminder, Reminder.referral_id.in_(referral_ids))
    removed["referral_events"] = _delete_where(
        session, ReferralEvent, ReferralEvent.referral_id.in_(referral_ids)
    )
    removed["referrals"] = _delete_where(session, Referral, Referral.user_id == user.id)
    removed["explanations"] = _delete_where(
        session, Explanation, Explanation.assessment_id.in_(assessment_ids)
    )
    removed["workflow_traces"] = _delete_where(
        session, WorkflowTrace, WorkflowTrace.assessment_id.in_(assessment_ids)
    )
    removed["clinician_reviews"] = _delete_where(
        session, ClinicianReview, ClinicianReview.assessment_id.in_(assessment_ids)
    )
    removed["assessments"] = _delete_where(session, Assessment, Assessment.user_id == user.id)
    removed["intake_answers"] = _delete_where(
        session, IntakeAnswers, IntakeAnswers.user_id == user.id
    )
    removed["shares"] = _delete_where(
        session,
        Share,
        (Share.user_id == user.id) | (Share.recipient_id == user.id),
    )
    user.contact_encrypted = None
    anonymized = (
        session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.actor_id == user.id)
        )
        or 0
    )
    session.execute(update(AuditLog).where(AuditLog.actor_id == user.id).values(actor_id=None))
    consents_kept = session.scalar(
        select(func.count()).select_from(Consent).where(Consent.user_id == user.id)
    )
    if hard:
        removed["consents"] = _delete_where(session, Consent, Consent.user_id == user.id)
        session.delete(user)
        removed["users"] = 1
        consents_kept = 0
    else:
        user.deleted_at = moment
        removed["users"] = 0
    session.flush()
    return DeleteResponse(
        removed=removed, anonymized_audit_entries=anonymized, consents_kept=consents_kept or 0
    )


def _delete_where(session: Session, model: type[ModelT], criterion: ColumnElement[bool]) -> int:
    """Delete rows matching one criterion.

    Args:
        session: Database session.
        model: Mapped model class.
        criterion: WHERE criterion.

    Returns:
        Deleted row count.
    """
    rows = session.scalars(select(model).where(criterion)).all()
    for row in rows:
        session.delete(row)
    return len(rows)
