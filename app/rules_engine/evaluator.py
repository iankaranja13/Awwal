"""Pure condition evaluation and derived-field computation."""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeGuard

from app.core.enums import ItemStatus
from app.rules_engine.models import Condition, Criterion, ItemAnswer, LogicGroup, Operator

logger = logging.getLogger("awwal.rules_engine")


@dataclass(frozen=True)
class ConditionOutcome:
    """Three-valued outcome of one criterion evaluation."""

    value: bool | None
    decisive: frozenset[str]
    refs: frozenset[str]


def _is_number(value: object) -> TypeGuard[int | float]:
    """Check for a real number that is not a boolean.

    Args:
        value: Value to check.

    Returns:
        True for int/float values excluding booleans.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _values_equal(left: object, right: object) -> bool:
    """Compare rule values with strict boolean handling.

    Python equates True with 1, so booleans only ever match booleans here.

    Args:
        left: Answered value.
        right: Rule value.

    Returns:
        True when the values match under strict typing.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if _is_number(left) and _is_number(right):
        return left == right
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    if left is None or right is None:
        return left is None and right is None
    return type(left) is type(right) and left == right


def _compare_ordered(op: Operator, field: str, actual: object, expected: object) -> bool:
    """Compare two numeric values with an ordering operator.

    Args:
        op: Ordering operator.
        field: Field name for logging (values are never logged).
        actual: Answered value.
        expected: Rule value.

    Returns:
        Comparison result, or false when either side is not numeric.
    """
    if not _is_number(actual) or not _is_number(expected):
        logger.warning("ordered comparison on non-numeric value", extra={"field": field})
        return False
    if op == Operator.GTE:
        return actual >= expected
    if op == Operator.LTE:
        return actual <= expected
    if op == Operator.GT:
        return actual > expected
    return actual < expected


def _apply_operator(op: Operator, field: str, actual: object, expected: object) -> bool:
    """Apply one operator to an answered value.

    Args:
        op: Operator to apply.
        field: Field name for logging (values are never logged).
        actual: Answered value from the intake.
        expected: Literal (param-resolved) rule value.

    Returns:
        Comparison result; type mismatches compare as false.
    """
    if op == Operator.EQ:
        return _values_equal(actual, expected)
    if op == Operator.NEQ:
        return not _values_equal(actual, expected)
    if op == Operator.IN:
        return isinstance(expected, list) and any(_values_equal(actual, item) for item in expected)
    if op == Operator.NOT_IN:
        return isinstance(expected, list) and not any(
            _values_equal(actual, item) for item in expected
        )
    if op in (Operator.GTE, Operator.LTE, Operator.GT, Operator.LT):
        return _compare_ordered(op, field, actual, expected)
    return actual is not None


def evaluate_condition(
    condition: Condition,
    answers: Mapping[str, ItemAnswer],
    derived: Mapping[str, float | None],
) -> ConditionOutcome:
    """Evaluate one atomic condition with three-valued logic.

    Unanswered fields make the outcome unknown rather than false.

    Args:
        condition: Condition to evaluate.
        answers: Answers by item id.
        derived: Derived values by field name.

    Returns:
        Outcome with value, decisive fields and referenced fields.
    """
    field = condition.field
    if field in derived:
        derived_value = derived[field]
        if derived_value is None:
            return ConditionOutcome(value=None, decisive=frozenset(), refs=frozenset())
        actual: object = derived_value
    else:
        answer = answers.get(field)
        if answer is None or answer.status != ItemStatus.ANSWERED:
            return ConditionOutcome(value=None, decisive=frozenset(), refs=frozenset())
        actual = answer.value
    if _apply_operator(condition.op, field, actual, condition.value):
        return ConditionOutcome(value=True, decisive=frozenset({field}), refs=frozenset({field}))
    return ConditionOutcome(value=False, decisive=frozenset(), refs=frozenset({field}))


def _combine_all(outcomes: list[ConditionOutcome]) -> ConditionOutcome:
    """Combine children with Kleene AND.

    Args:
        outcomes: Child outcomes.

    Returns:
        Combined outcome.
    """
    refs = frozenset().union(*(outcome.refs for outcome in outcomes))
    if all(outcome.value is True for outcome in outcomes):
        decisive = frozenset().union(*(outcome.decisive for outcome in outcomes))
        return ConditionOutcome(value=True, decisive=decisive, refs=refs)
    if any(outcome.value is False for outcome in outcomes):
        return ConditionOutcome(value=False, decisive=frozenset(), refs=refs)
    return ConditionOutcome(value=None, decisive=frozenset(), refs=refs)


def _combine_any(outcomes: list[ConditionOutcome]) -> ConditionOutcome:
    """Combine children with Kleene OR.

    Args:
        outcomes: Child outcomes.

    Returns:
        Combined outcome.
    """
    refs = frozenset().union(*(outcome.refs for outcome in outcomes))
    if any(outcome.value is True for outcome in outcomes):
        decisive = frozenset().union(*(outcome.decisive for outcome in outcomes))
        return ConditionOutcome(value=True, decisive=decisive, refs=refs)
    if all(outcome.value is False for outcome in outcomes):
        return ConditionOutcome(value=False, decisive=frozenset(), refs=refs)
    return ConditionOutcome(value=None, decisive=frozenset(), refs=refs)


def _evaluate_group(
    group: LogicGroup,
    answers: Mapping[str, ItemAnswer],
    derived: Mapping[str, float | None],
) -> ConditionOutcome:
    """Evaluate one logic group.

    Args:
        group: Logic group to evaluate.
        answers: Answers by item id.
        derived: Derived values by field name.

    Returns:
        Combined outcome.

    Raises:
        ValueError: If the group holds no branch (rejected by the loader).
    """
    if group.all is not None:
        children = [evaluate_criterion(item, answers, derived) for item in group.all]
        return _combine_all(children)
    if group.any is not None:
        children = [evaluate_criterion(item, answers, derived) for item in group.any]
        return _combine_any(children)
    if group.negation is None:  # Defensive; the loader rejects empty groups.
        raise ValueError("Logic group has no branch.")
    child = evaluate_criterion(group.negation, answers, derived)
    if child.value is None:
        return ConditionOutcome(value=None, decisive=frozenset(), refs=child.refs)
    if child.value:
        return ConditionOutcome(value=False, decisive=frozenset(), refs=child.refs)
    return ConditionOutcome(value=True, decisive=child.refs, refs=child.refs)


def evaluate_criterion(
    criterion: Criterion,
    answers: Mapping[str, ItemAnswer],
    derived: Mapping[str, float | None],
) -> ConditionOutcome:
    """Evaluate any criterion (condition or logic group).

    Args:
        criterion: Criterion to evaluate.
        answers: Answers by item id.
        derived: Derived values by field name.

    Returns:
        Outcome with value, decisive fields and referenced fields.

    Raises:
        TypeError: If the node type is unknown (unreachable for valid rules).
    """
    if isinstance(criterion, Condition):
        return evaluate_condition(criterion, answers, derived)
    if isinstance(criterion, LogicGroup):
        return _evaluate_group(criterion, answers, derived)
    raise TypeError(f"Unknown criterion node: {type(criterion).__name__}.")


def _numeric_answer(answers: Mapping[str, ItemAnswer], field: str) -> float | None:
    """Read one answered numeric value.

    Args:
        answers: Answers by item id.
        field: Item id to read.

    Returns:
        The value as a float, or None when missing or non-numeric.
    """
    answer = answers.get(field)
    if answer is None or answer.status != ItemStatus.ANSWERED:
        return None
    if isinstance(answer.value, bool) or not isinstance(answer.value, (int, float)):
        return None
    return float(answer.value)


def compute_bmi(answers: Mapping[str, ItemAnswer]) -> float | None:
    """Compute BMI from answered height and weight.

    The value is rounded to one decimal before use so the stored value and
    the threshold comparison always agree.

    Args:
        answers: Answers by item id.

    Returns:
        Rounded BMI, or None when it cannot be computed.
    """
    height = _numeric_answer(answers, "height_cm")
    weight = _numeric_answer(answers, "weight_kg")
    if height is None or weight is None or height <= 0 or weight <= 0:
        return None
    return round(weight / ((height / 100.0) ** 2), 1)


DERIVED_FIELDS: dict[str, Callable[[Mapping[str, ItemAnswer]], float | None]] = {"bmi": compute_bmi}


def compute_derived(answers: Mapping[str, ItemAnswer]) -> dict[str, float | None]:
    """Compute every derived field.

    Args:
        answers: Answers by item id.

    Returns:
        Derived values by field name (None when uncomputable).
    """
    return {name: computer(answers) for name, computer in DERIVED_FIELDS.items()}
