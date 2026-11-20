"""Explanation output contract (shared by templates and the LLM)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ExplanationSource, FlagState, Language, Route


class ExplainedFlag(BaseModel):
    """Plain-language explanation for one flag."""

    model_config = ConfigDict(frozen=True)

    flag_id: str = Field(min_length=1, description="Explained flag id.")
    explanation: str = Field(min_length=1, description="Plain-language explanation.")
    unknowns: list[str] = Field(default_factory=list, description="Open unknowns.")
    modifiable_note: str | None = Field(default=None, description="Modifiable note, if any.")
    sources: list[str] = Field(default_factory=list, description="Cited excerpt ids.")


class ExplainerOutput(BaseModel):
    """Validated explanation document."""

    model_config = ConfigDict(frozen=True)

    language: Language = Field(description="Explanation language.")
    summary: str = Field(min_length=1, description="Overall summary.")
    flags: list[ExplainedFlag] = Field(description="Per-flag explanations.")
    next_step_text: str = Field(min_length=1, description="Next step consistent with the route.")
    disclaimer: str = Field(min_length=1, description="Screening disclaimer.")


class BriefFlag(BaseModel):
    """One flag entry in a clinician brief."""

    model_config = ConfigDict(frozen=True)

    flag_id: str = Field(min_length=1, description="Flag id.")
    state: FlagState = Field(description="Three-state outcome.")
    label: str = Field(description="Display label.")
    source: str = Field(description="Guideline source hint (unvalidated).")
    note: str | None = Field(default=None, description="Short note, if any.")
    sources: list[str] = Field(default_factory=list, description="Cited excerpt ids.")


class BriefOutput(BaseModel):
    """Validated clinician brief document."""

    model_config = ConfigDict(frozen=True)

    language: Language = Field(description="Brief language.")
    reason_for_contact: str = Field(min_length=1, description="Reason for contact.")
    flags: list[BriefFlag] = Field(description="Flag entries.")
    missing_information: list[str] = Field(default_factory=list, description="Missing items.")
    route: Route = Field(description="Selected route.")
    route_rationale: str = Field(min_length=1, description="Route rationale.")
    scope_note: str = Field(min_length=1, description="Record scope note.")


class ValidatorReport(BaseModel):
    """Validator outcome."""

    model_config = ConfigDict(frozen=True)

    ok: bool = Field(description="Whether validation passed.")
    errors: list[str] = Field(default_factory=list, description="Rejection reasons.")


class ExplainRequest(BaseModel):
    """Explanation regeneration request."""

    model_config = ConfigDict(frozen=True)

    assessment_id: UUID = Field(description="Assessment id.")
    language: Language | None = Field(default=None, description="Requested language.")


class ExplainResponse(BaseModel):
    """Regenerated explanation."""

    model_config = ConfigDict(frozen=True)

    assessment_id: UUID = Field(description="Assessment id.")
    language: Language = Field(description="Explanation language.")
    explanation: ExplainerOutput = Field(description="Explanation document.")
    source: ExplanationSource = Field(description="Explanation origin.")
    used_fallback: bool = Field(description="Whether templates were used.")
    model: str | None = Field(default=None, description="Model name, if any.")
    validator: ValidatorReport | None = Field(default=None, description="Validator outcome.")


class BriefRequest(BaseModel):
    """Clinician brief request."""

    model_config = ConfigDict(frozen=True)

    assessment_id: UUID = Field(description="Assessment id.")
    language: Language | None = Field(default=None, description="Requested language.")


class BriefResponse(BaseModel):
    """Generated clinician brief."""

    model_config = ConfigDict(frozen=True)

    assessment_id: UUID = Field(description="Assessment id.")
    language: Language = Field(description="Brief language.")
    brief: BriefOutput = Field(description="Brief document.")
    source: ExplanationSource = Field(description="Brief origin.")
    used_fallback: bool = Field(description="Whether templates were used.")
    model: str = Field(description="Model name attempted.")
