"""Assessment and trace response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ExplanationSource, FlagState, Language, Route


class AssessFlag(BaseModel):
    """One flag as served in assessment responses."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Flag id.")
    state: FlagState = Field(description="Three-state outcome.")
    domain: str = Field(description="Clinical domain.")
    label: str = Field(description="Display label in the response language.")
    reason_fields: list[str] = Field(default_factory=list, description="Decisive fields.")
    missing_fields: list[str] = Field(default_factory=list, description="Missing required fields.")
    modifiable: bool = Field(description="Whether the user can act on this factor.")
    source: str = Field(description="Guideline source hint (unvalidated).")
    requires_clinical_validation: bool = Field(description="True until a validation flow exists.")
    explanation: str = Field(description="Plain-language explanation.")
    why_we_ask: str | None = Field(default=None, description="Why text for missing fields.")


class MissingItem(BaseModel):
    """One missing key item with its reason."""

    model_config = ConfigDict(frozen=True)

    item_id: str = Field(description="Missing item id.")
    why_we_ask: str = Field(description="Why text in the response language.")


class NextStep(BaseModel):
    """Next step for the selected route."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(description="Next-step text.")
    requires_clinician_review: bool = Field(description="Whether sign-off gates confirmation.")
    actions: list[str] = Field(default_factory=list, description="Frontend action codes.")


class StaticSafetyMessage(BaseModel):
    """Static urgent safety message."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Static message id.")
    title: str = Field(description="Message title.")
    body: str = Field(description="Message body.")


class AssessResponse(BaseModel):
    """Full assessment response."""

    model_config = ConfigDict(frozen=True)

    assessment_id: UUID = Field(description="Assessment id.")
    rules_version: str = Field(description="Combined rule version string.")
    language: Language = Field(description="Response language.")
    urgent: bool = Field(description="Whether a red flag short-circuited the pipeline.")
    route: Route = Field(description="Selected route.")
    route_reason: list[str] = Field(default_factory=list, description="Driver rule ids.")
    flags: list[AssessFlag] = Field(default_factory=list, description="Flag outcomes.")
    missing_items: list[MissingItem] = Field(default_factory=list, description="Missing key items.")
    next_step: NextStep = Field(description="Next step.")
    static_safety_message: StaticSafetyMessage | None = Field(
        default=None, description="Urgent static message."
    )
    disclaimer: str = Field(description="Screening disclaimer.")
    explanation_source: ExplanationSource = Field(description="Explanation origin.")
    trace_id: UUID = Field(description="Workflow trace id.")


class TraceStep(BaseModel):
    """One workflow trace step."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Step name.")
    status: str = Field(description="Step status.")
    started_at: datetime = Field(description="Step start (UTC).")
    duration_ms: float = Field(description="Step duration in milliseconds.")
    rules_version: str = Field(description="Rule version in force.")
    detail: dict[str, Any] = Field(default_factory=dict, description="Step detail.")


class TraceResponse(BaseModel):
    """Workflow trace response."""

    model_config = ConfigDict(frozen=True)

    trace_id: UUID = Field(description="Trace id.")
    assessment_id: UUID = Field(description="Assessment id.")
    steps: list[TraceStep] = Field(description="Recorded steps in order.")
    duration_ms: float = Field(description="Total milliseconds across steps.")
