"""Pydantic models for rule files and engine evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import FlagState, ItemStatus, Route


class Operator(StrEnum):
    """Comparison operators allowed in rule conditions."""

    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"
    GTE = "gte"
    LTE = "lte"
    GT = "gt"
    LT = "lt"
    EXISTS = "exists"


class Label(BaseModel):
    """Bilingual display text."""

    model_config = ConfigDict(frozen=True)

    en: str = Field(min_length=1, description="English text.")
    ar: str = Field(min_length=1, description="Arabic text.")


class Condition(BaseModel):
    """One atomic field comparison."""

    model_config = ConfigDict(frozen=True)

    field: str = Field(min_length=1, description="Intake item id or derived field name.")
    op: Operator = Field(description="Comparison operator.")
    value: Any = Field(default=None, description="Literal comparison value.")
    param: str | None = Field(default=None, description="Parameter name from the params file.")

    @model_validator(mode="after")
    def _check_value_or_param(self) -> Condition:
        """Reject ambiguous or incomplete comparisons.

        Returns:
            The validated condition.

        Raises:
            ValueError: If the value/param combination is invalid for the operator.
        """
        if self.op == Operator.EXISTS:
            if self.value is not None or self.param is not None:
                raise ValueError("exists takes no value or param.")
            return self
        if self.value is None and self.param is None:
            raise ValueError("non-exists conditions need value or param.")
        if self.value is not None and self.param is not None:
            raise ValueError("conditions take value or param, not both.")
        if self.op in (Operator.IN, Operator.NOT_IN):
            if self.param is not None:
                raise ValueError("in/not_in need a literal list value, not a param.")
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("in/not_in need a non-empty list value.")
        if self.op in (Operator.GTE, Operator.LTE, Operator.GT, Operator.LT):
            if self.value is not None and (
                isinstance(self.value, bool) or not isinstance(self.value, (int, float))
            ):
                raise ValueError("ordering comparisons need a numeric value.")
        return self


class LogicGroup(BaseModel):
    """Boolean combination of criteria."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    all: list[Criterion] | None = Field(default=None, description="Criteria that must all hold.")
    any: list[Criterion] | None = Field(
        default=None, description="Criteria of which one must hold."
    )
    negation: Criterion | None = Field(
        default=None, alias="not", description="Criterion that must not hold."
    )

    @model_validator(mode="after")
    def _check_exactly_one(self) -> LogicGroup:
        """Reject empty or ambiguous groups.

        Returns:
            The validated group.

        Raises:
            ValueError: If the group does not hold exactly one branch.
        """
        branches = [self.all, self.any, self.negation]
        if sum(branch is not None for branch in branches) != 1:
            raise ValueError("logic groups need exactly one of all, any or not.")
        if self.all is not None and not self.all:
            raise ValueError("all needs a non-empty list.")
        if self.any is not None and not self.any:
            raise ValueError("any needs a non-empty list.")
        return self


Criterion: TypeAlias = Condition | LogicGroup

LogicGroup.model_rebuild()


class FlagRule(BaseModel):
    """One screening flag definition from the flags file."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", description="Stable flag id.")
    domain: str = Field(min_length=1, description="Clinical domain.")
    label: Label = Field(description="Bilingual display label.")
    required_fields: list[str] = Field(min_length=1, description="Intake items needed to assess.")
    present_when: Criterion = Field(description="Presence logic.")
    modifiable: bool = Field(description="Whether the user can act on this factor.")
    suggests_route: Route = Field(description="Route suggested when present.")
    is_ttc_criterion: bool = Field(default=False, description="Whether this is a TTC criterion.")
    key: bool = Field(default=True, description="Whether missing data forces provisional route.")
    snippet_id: str = Field(min_length=1, description="Explanation snippet id.")
    source: str = Field(min_length=1, description="Guideline source hint (unvalidated).")
    requires_clinical_validation: bool = Field(description="True until a validation flow exists.")
    needs_native_review: bool = Field(description="True until Arabic review exists.")


class RedFlagRule(BaseModel):
    """One red flag definition from the red-flags file."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", description="Stable red flag id.")
    label: Label = Field(description="Bilingual display label.")
    required_fields: list[str] = Field(min_length=1, description="Intake items needed to assess.")
    present_when: Criterion = Field(description="Presence logic.")
    static_message_id: str = Field(min_length=1, description="Static safety message id.")
    source: str = Field(min_length=1, description="Guideline source hint (unvalidated).")
    requires_clinical_validation: bool = Field(description="True until a validation flow exists.")
    needs_native_review: bool = Field(description="True until Arabic review exists.")


class RouteDef(BaseModel):
    """One route definition from the routes file."""

    model_config = ConfigDict(frozen=True)

    id: Route = Field(description="Route id.")
    precedence: int = Field(description="Higher wins when several flags are present.")
    requires_clinician_review: bool = Field(description="Whether sign-off gates confirmation.")
    label: Label = Field(description="Bilingual display label.")
    needs_native_review: bool = Field(description="True until Arabic review exists.")


class ParamDef(BaseModel):
    """One named parameter from the params file."""

    model_config = ConfigDict(frozen=True)

    value: int | float | str = Field(description="Parameter value (never a list).")
    description: str = Field(min_length=1, description="What the parameter means.")
    source: str = Field(min_length=1, description="Guideline source hint (unvalidated).")
    requires_clinical_validation: bool = Field(description="True until a validation flow exists.")


class FlagsFile(BaseModel):
    """Envelope for the flags file."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1, description="Rule file version.")
    flags: list[FlagRule] = Field(description="Flag definitions.")


class RedFlagsFile(BaseModel):
    """Envelope for the red-flags file."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1, description="Rule file version.")
    redflags: list[RedFlagRule] = Field(description="Red flag definitions.")


class RoutesFile(BaseModel):
    """Envelope for the routes file."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1, description="Rule file version.")
    routes: list[RouteDef] = Field(description="Route definitions.")


class ParamsFile(BaseModel):
    """Envelope for the params file."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1, description="Rule file version.")
    params: dict[str, ParamDef] = Field(description="Parameters by name.")


class ItemAnswer(BaseModel):
    """One stored intake answer."""

    model_config = ConfigDict(frozen=True)

    value: Any = Field(default=None, description="Provided answer value.")
    status: ItemStatus = Field(description="Answer status.")


class AssessmentInput(BaseModel):
    """Answers to evaluate."""

    model_config = ConfigDict(frozen=True)

    answers: dict[str, ItemAnswer] = Field(default_factory=dict, description="Answers by item id.")


class FlagResult(BaseModel):
    """Three-state outcome for one flag."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Flag id.")
    state: FlagState = Field(description="Three-state outcome.")
    domain: str = Field(description="Clinical domain.")
    label: Label = Field(description="Bilingual display label.")
    reason_fields: list[str] = Field(default_factory=list, description="Decisive fields.")
    missing_fields: list[str] = Field(default_factory=list, description="Missing required fields.")
    modifiable: bool = Field(description="Whether the user can act on this factor.")
    suggests_route: Route = Field(description="Route suggested when present.")
    snippet_id: str = Field(description="Explanation snippet id.")
    source: str = Field(description="Guideline source hint (unvalidated).")
    requires_clinical_validation: bool = Field(description="True until a validation flow exists.")


class RedFlagResult(BaseModel):
    """Outcome for one red flag."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Red flag id.")
    present: bool = Field(description="Whether the red flag is present.")
    missing_fields: list[str] = Field(default_factory=list, description="Missing required fields.")
    static_message_id: str = Field(description="Static safety message id.")


class EngineResult(BaseModel):
    """Full evaluation outcome for one answer set."""

    model_config = ConfigDict(frozen=True)

    rules_version: str = Field(description="Combined rule version string.")
    route: Route = Field(description="Selected route.")
    urgent: bool = Field(description="Whether a red flag short-circuited the pipeline.")
    route_reason: list[str] = Field(default_factory=list, description="Driver rule ids.")
    flags: list[FlagResult] = Field(default_factory=list, description="Flag outcomes.")
    red_flags: list[RedFlagResult] = Field(default_factory=list, description="Red flag outcomes.")
    red_flags_present: list[str] = Field(default_factory=list, description="Present red flag ids.")
    missing_items: list[str] = Field(default_factory=list, description="Missing key item ids.")
    derived_values: dict[str, float] = Field(default_factory=dict, description="Computed values.")
    static_message_id: str | None = Field(default=None, description="Urgent static message id.")


class RuleSet(BaseModel):
    """Loaded and validated rule set with params resolved."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(description="Combined rule version string.")
    flags: tuple[FlagRule, ...] = Field(default_factory=tuple, description="Flag definitions.")
    red_flags: tuple[RedFlagRule, ...] = Field(default_factory=tuple, description="Red flags.")
    routes: tuple[RouteDef, ...] = Field(default_factory=tuple, description="Route definitions.")
    params: dict[str, ParamDef] = Field(default_factory=dict, description="Raw parameters.")
