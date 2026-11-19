"""Referral request and response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ReferralStatus, ReferralType, ReviewDecision


class ContactIn(BaseModel):
    """Contact details collected at booking."""

    model_config = ConfigDict(frozen=True)

    name: str | None = Field(default=None, max_length=128, description="Contact name.")
    phone: str | None = Field(default=None, max_length=32, description="Contact phone.")
    email: str | None = Field(default=None, max_length=320, description="Contact email.")


class ReferralCreate(BaseModel):
    """Referral creation request."""

    model_config = ConfigDict(frozen=True)

    assessment_id: UUID = Field(description="Assessment id.")
    type: ReferralType = Field(description="Service type.")
    provider_id: UUID | None = Field(default=None, description="Chosen provider id.")
    preferred_time: datetime | None = Field(default=None, description="Preferred time.")
    contact: ContactIn | None = Field(default=None, description="Contact details.")


class StatusUpdate(BaseModel):
    """Referral status transition request."""

    model_config = ConfigDict(frozen=True)

    to_status: ReferralStatus = Field(description="Target status.")
    appointment_time: datetime | None = Field(default=None, description="Appointment time.")
    outcome_note: str | None = Field(default=None, max_length=5000, description="Outcome note.")


class ReferralEventOut(BaseModel):
    """One referral transition event."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Event id.")
    from_status: ReferralStatus | None = Field(description="Previous status.")
    to_status: ReferralStatus = Field(description="New status.")
    actor_id: UUID | None = Field(description="Acting user id (None for system).")
    at: datetime = Field(description="Transition time (UTC).")


class QueueEntry(BaseModel):
    """One clinician queue entry."""

    model_config = ConfigDict(frozen=True)

    referral_id: UUID = Field(description="Referral id.")
    assessment_id: UUID = Field(description="Assessment id.")
    user_handle: str = Field(description="User handle.")
    type: ReferralType = Field(description="Service type.")
    status: ReferralStatus = Field(description="Current status.")
    route: str = Field(description="Assessment route.")
    created_at: datetime = Field(description="Referral creation time (UTC).")


class ReferralOut(BaseModel):
    """One referral with its transition history."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Referral id.")
    assessment_id: UUID = Field(description="Assessment id.")
    user_id: UUID = Field(description="Owning user id.")
    type: ReferralType = Field(description="Service type.")
    provider_id: UUID | None = Field(description="Chosen provider id.")
    status: ReferralStatus = Field(description="Current status.")
    preferred_time: datetime | None = Field(description="Preferred time.")
    appointment_time: datetime | None = Field(description="Appointment time.")
    outcome_note: str | None = Field(description="Decrypted outcome note.")
    created_at: datetime = Field(description="Creation time (UTC).")
    updated_at: datetime = Field(description="Update time (UTC).")
    events: list[ReferralEventOut] = Field(default_factory=list, description="Transitions.")


class ReviewRequest(BaseModel):
    """Clinician review request."""

    model_config = ConfigDict(frozen=True)

    assessment_id: UUID = Field(description="Assessment id.")
    decision: ReviewDecision = Field(description="Review decision.")
    edits: dict[str, Any] | None = Field(default=None, description="Structured edits.")
    notes: str | None = Field(default=None, max_length=5000, description="Review notes.")


class ReviewResponse(BaseModel):
    """Submitted review with referral outcome."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Review id.")
    assessment_id: UUID = Field(description="Assessment id.")
    reviewer_id: UUID = Field(description="Reviewing clinician id.")
    decision: ReviewDecision = Field(description="Decision.")
    signed_off_at: datetime | None = Field(description="Sign-off time (UTC).")
    referral_id: UUID = Field(description="Affected referral id.")
    referral_status: ReferralStatus = Field(description="Referral status after review.")


class LoginRequest(BaseModel):
    """Role account login request."""

    model_config = ConfigDict(frozen=True)

    handle: str = Field(min_length=1, max_length=64, description="Account handle.")
    password: str = Field(min_length=1, max_length=128, description="Account password.")
