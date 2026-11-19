"""Three-state flag and red-flag evaluation."""

from collections.abc import Mapping

from app.core.enums import FlagState, ItemStatus
from app.rules_engine.evaluator import evaluate_criterion
from app.rules_engine.models import (
    AssessmentInput,
    FlagResult,
    FlagRule,
    ItemAnswer,
    RedFlagResult,
    RedFlagRule,
)


def _is_answered(answers: Mapping[str, ItemAnswer], field: str) -> bool:
    """Check whether one intake item has an answered value.

    Args:
        answers: Answers by item id.
        field: Item id to check.

    Returns:
        True only when the item exists with answered status.
    """
    answer = answers.get(field)
    return answer is not None and answer.status == ItemStatus.ANSWERED


def evaluate_flag(
    rule: FlagRule, inputs: AssessmentInput, derived: Mapping[str, float | None]
) -> FlagResult:
    """Evaluate one flag with three-state logic.

    A true presence condition wins even when other required fields are
    missing; otherwise any missing required field makes the flag
    not assessable instead of silently negative.

    Args:
        rule: Flag definition.
        inputs: Answers to evaluate.
        derived: Derived values by field name.

    Returns:
        Three-state outcome for the flag.
    """
    outcome = evaluate_criterion(rule.present_when, inputs.answers, derived)
    if outcome.value is True:
        state = FlagState.PRESENT
        reason_fields = sorted(outcome.decisive)
        missing_fields: list[str] = []
    else:
        missing_fields = [
            field for field in rule.required_fields if not _is_answered(inputs.answers, field)
        ]
        if missing_fields:
            state = FlagState.NOT_ASSESSABLE
            reason_fields = []
        else:
            state = FlagState.NOT_PRESENT_FROM_PROVIDED_DATA
            reason_fields = []
    return FlagResult(
        id=rule.id,
        state=state,
        domain=rule.domain,
        label=rule.label,
        reason_fields=reason_fields,
        missing_fields=missing_fields,
        modifiable=rule.modifiable,
        suggests_route=rule.suggests_route,
        snippet_id=rule.snippet_id,
        source=rule.source,
        requires_clinical_validation=rule.requires_clinical_validation,
    )


def evaluate_red_flag(
    rule: RedFlagRule, inputs: AssessmentInput, derived: Mapping[str, float | None]
) -> RedFlagResult:
    """Evaluate one red flag for presence and missing data.

    Args:
        rule: Red flag definition.
        inputs: Answers to evaluate.
        derived: Derived values by field name.

    Returns:
        Presence outcome with missing required fields.
    """
    outcome = evaluate_criterion(rule.present_when, inputs.answers, derived)
    missing_fields = [
        field for field in rule.required_fields if not _is_answered(inputs.answers, field)
    ]
    return RedFlagResult(
        id=rule.id,
        present=outcome.value is True,
        missing_fields=missing_fields,
        static_message_id=rule.static_message_id,
    )
