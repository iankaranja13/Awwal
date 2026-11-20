"""Privacy request and response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEntryOut(BaseModel):
    """One audit entry."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Entry id.")
    actor_role: str = Field(description="Acting role.")
    action: str = Field(description="Action name.")
    object_type: str = Field(description="Object type.")
    object_id: UUID | None = Field(description="Object id.")
    at: datetime = Field(description="Entry time (UTC).")
    detail: dict[str, Any] = Field(description="Non-sensitive context.")


class PrivacySection(BaseModel):
    """One privacy copy section."""

    model_config = ConfigDict(frozen=True)

    heading: str = Field(description="Section heading.")
    body: str = Field(description="Section body.")


class PrivacyCopy(BaseModel):
    """Privacy and data-use copy in one language."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(description="Page title.")
    sections: list[PrivacySection] = Field(description="Sections.")


class ExportResponse(BaseModel):
    """Full export of one user's data."""

    model_config = ConfigDict(frozen=True)

    consents: list[dict[str, Any]] = Field(description="Consent ledger entries.")
    intake: dict[str, Any] = Field(description="Decrypted intake answers.")
    assessments: list[dict[str, Any]] = Field(description="Assessments with explanations.")
    referrals: list[dict[str, Any]] = Field(description="Referrals with events.")
    reminders: list[dict[str, Any]] = Field(description="Reminders.")
    shares: list[dict[str, Any]] = Field(description="Share grants given.")
    audit: list[AuditEntryOut] = Field(description="Own audit entries.")


class DeleteResponse(BaseModel):
    """User data deletion summary."""

    model_config = ConfigDict(frozen=True)

    removed: dict[str, int] = Field(description="Removed row counts by table.")
    anonymized_audit_entries: int = Field(description="Anonymised audit entries.")
    consents_kept: int = Field(description="Retained consent receipts.")
