"""Referral lifecycle models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import ReferralStatus, ReferralType, ReviewDecision
from app.models.base import Base
from app.models.types import AwareDateTime


class Referral(Base):
    """One referral with clinician-gated confirmation."""

    __tablename__ = "referrals"
    __table_args__ = (
        CheckConstraint(
            "type IN ('teleconsult', 'blood_test', 'sample_collection', 'in_person')",
            name="ck_referrals_type",
        ),
        CheckConstraint(
            "status IN ('proposed', 'clinician_review', 'confirmed', 'booked', "
            "'attended', 'result_explained', 'closed', 'cancelled', 'no_show')",
            name="ck_referrals_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[ReferralType] = mapped_column(
        SAEnum(
            ReferralType,
            native_enum=False,
            validate_strings=True,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("providers.id"), nullable=True)
    status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(
            ReferralStatus,
            native_enum=False,
            validate_strings=True,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    preferred_time: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    appointment_time: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    outcome_note_encrypted: Mapped[str | None] = mapped_column("outcome_note", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class ReferralEvent(Base):
    """One referral transition (never updated or deleted)."""

    __tablename__ = "referral_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    referral_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referrals.id"), index=True)
    from_status: Mapped[ReferralStatus | None] = mapped_column(
        SAEnum(
            ReferralStatus,
            native_enum=False,
            validate_strings=True,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=True,
    )
    to_status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(
            ReferralStatus,
            native_enum=False,
            validate_strings=True,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)


class Reminder(Base):
    """One simulated reminder (no real messaging)."""

    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    referral_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referrals.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    due_at: Mapped[datetime] = mapped_column(AwareDateTime, nullable=False)
    simulated_sent_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)


class ClinicianReview(Base):
    """One clinician review with optional sign-off."""

    __tablename__ = "clinician_reviews"
    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected')", name="ck_reviews_decision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[ReviewDecision] = mapped_column(
        SAEnum(
            ReviewDecision,
            native_enum=False,
            validate_strings=True,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    edits: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    notes_encrypted: Mapped[str | None] = mapped_column("notes", Text, nullable=True)
    signed_off_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utc_now, nullable=False)
