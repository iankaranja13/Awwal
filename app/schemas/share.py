"""Share request and response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShareScope(BaseModel):
    """Share scope: everything or listed assessments."""

    model_config = ConfigDict(frozen=True)

    all: bool = Field(default=False, description="Whether all assessments are shared.")
    assessment_ids: list[UUID] = Field(default_factory=list, description="Shared assessment ids.")

    @model_validator(mode="after")
    def _check_exactly_one(self) -> "ShareScope":
        """Reject empty or ambiguous scopes.

        Returns:
            The validated scope.

        Raises:
            ValueError: If the scope is not exactly one mode.
        """
        if self.all == bool(self.assessment_ids):
            raise ValueError("scope needs all=true or assessment ids, not both or neither.")
        return self


class ShareCreate(BaseModel):
    """Share creation request."""

    model_config = ConfigDict(frozen=True)

    recipient_id: UUID = Field(description="Clinician recipient id.")
    scope: ShareScope = Field(description="Share scope.")
    expires_in_hours: int = Field(gt=0, le=720, description="Lifetime in hours (max 30 days).")


class ShareOut(BaseModel):
    """One share grant."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Share id.")
    recipient_id: UUID = Field(description="Clinician recipient id.")
    scope: ShareScope = Field(description="Share scope.")
    expires_at: datetime = Field(description="Expiry time (UTC).")
    revoked_at: datetime | None = Field(description="Revocation time (UTC).")
    created_at: datetime = Field(description="Creation time (UTC).")
