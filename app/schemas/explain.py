"""Explanation output contract (shared by templates and the LLM)."""

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Language


class ExplainedFlag(BaseModel):
    """Plain-language explanation for one flag."""

    model_config = ConfigDict(frozen=True)

    flag_id: str = Field(min_length=1, description="Explained flag id.")
    explanation: str = Field(min_length=1, description="Plain-language explanation.")
    unknowns: list[str] = Field(default_factory=list, description="Open unknowns.")
    modifiable_note: str | None = Field(default=None, description="Modifiable note, if any.")


class ExplainerOutput(BaseModel):
    """Validated explanation document."""

    model_config = ConfigDict(frozen=True)

    language: Language = Field(description="Explanation language.")
    summary: str = Field(min_length=1, description="Overall summary.")
    flags: list[ExplainedFlag] = Field(description="Per-flag explanations.")
    next_step_text: str = Field(min_length=1, description="Next step consistent with the route.")
    disclaimer: str = Field(min_length=1, description="Screening disclaimer.")
