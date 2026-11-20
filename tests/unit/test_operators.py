"""Operator and combinator truth-table behaviour."""

from typing import Any

import pytest

from app.rules_engine.evaluator import evaluate_condition, evaluate_criterion
from app.rules_engine.models import Condition, LogicGroup, Operator
from tests.unit.rule_helpers import answered, assessment


def _condition(field: str, op: Operator, value: Any = None) -> Condition:
    if op == Operator.EXISTS:
        return Condition(field=field, op=op)
    return Condition(field=field, op=op, value=value)


def _value_of(field: str, op: Operator, value: Any, actual: Any) -> bool | None:
    condition = _condition(field, op, value)
    inputs = assessment(**{field: answered(actual)})
    return evaluate_condition(condition, inputs.answers, {}).value


def test_eq_matches_booleans() -> None:
    """Match boolean equality strictly."""
    assert _value_of("flag", Operator.EQ, True, True) is True
    assert _value_of("flag", Operator.EQ, True, False) is False


def test_eq_rejects_bool_number_mix() -> None:
    """Refuse to equate True with 1."""
    assert _value_of("flag", Operator.EQ, True, 1) is False
    assert _value_of("flag", Operator.EQ, 1, True) is False


def test_eq_matches_numbers_and_strings() -> None:
    """Match numeric and string equality."""
    assert _value_of("months", Operator.EQ, 12, 12) is True
    assert _value_of("months", Operator.EQ, 12, 12.0) is True
    assert _value_of("choice", Operator.EQ, "yes", "yes") is True
    assert _value_of("choice", Operator.EQ, "yes", "no") is False
    assert _value_of("choice", Operator.EQ, "yes", True) is False


def test_neq_negates_equality() -> None:
    """Negate strict equality."""
    assert _value_of("flag", Operator.NEQ, True, False) is True
    assert _value_of("flag", Operator.NEQ, True, True) is False
    assert _value_of("flag", Operator.NEQ, True, 1) is True


def test_in_checks_membership() -> None:
    """Check list membership strictly."""
    assert _value_of("use", Operator.IN, ["former", "current"], "current") is True
    assert _value_of("use", Operator.IN, ["former", "current"], "never") is False
    assert _value_of("flag", Operator.IN, [True], 1) is False


def test_not_in_negates_membership() -> None:
    """Negate list membership."""
    assert _value_of("use", Operator.NOT_IN, ["never"], "current") is True
    assert _value_of("use", Operator.NOT_IN, ["never"], "never") is False


def test_ordered_operators_compare_numbers() -> None:
    """Compare numeric boundaries inclusively and exclusively."""
    assert _value_of("months", Operator.GTE, 12, 12) is True
    assert _value_of("months", Operator.GTE, 12, 11) is False
    assert _value_of("months", Operator.LTE, 12, 12) is True
    assert _value_of("months", Operator.LTE, 12, 13) is False
    assert _value_of("months", Operator.GT, 12, 13) is True
    assert _value_of("months", Operator.GT, 12, 12) is False
    assert _value_of("months", Operator.LT, 12, 11) is True
    assert _value_of("months", Operator.LT, 12, 12) is False


def test_ordered_operators_reject_non_numeric() -> None:
    """Compare non-numeric ordered values as false."""
    assert _value_of("months", Operator.GTE, 12, "many") is False
    assert _value_of("months", Operator.GTE, 12, True) is False
    assert _value_of("months", Operator.GTE, 12, None) is False


def test_exists_checks_answered_values() -> None:
    """Report existence only for answered non-null values."""
    condition = _condition("note", Operator.EXISTS)
    present = assessment(note=answered("something"))
    assert evaluate_condition(condition, present.answers, {}).value is True
    null = assessment(note=answered(None))
    assert evaluate_condition(condition, null.answers, {}).value is False
    assert evaluate_condition(condition, assessment().answers, {}).value is None


def test_missing_field_is_unknown() -> None:
    """Evaluate missing fields as unknown rather than false."""
    condition = _condition("flag", Operator.EQ, True)
    assert evaluate_condition(condition, assessment().answers, {}).value is None


ALL_CASES = [
    (True, True, True),
    (True, False, False),
    (True, None, None),
    (False, True, False),
    (False, False, False),
    (False, None, False),
    (None, True, None),
    (None, False, False),
    (None, None, None),
]

ANY_CASES = [
    (True, True, True),
    (True, False, True),
    (True, None, True),
    (False, True, True),
    (False, False, False),
    (False, None, None),
    (None, True, True),
    (None, False, None),
    (None, None, None),
]

NOT_CASES = [(True, False), (False, True), (None, None)]


def _inputs_for(first: bool | None, second: bool | None) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    if first is not None:
        answers["first"] = answered(first)
    if second is not None:
        answers["second"] = answered(second)
    return answers


@pytest.mark.parametrize(("first", "second", "expected"), ALL_CASES)
def test_all_truth_table(first: bool | None, second: bool | None, expected: bool | None) -> None:
    """Combine all branches with Kleene AND."""
    group = LogicGroup(
        all=[_condition("first", Operator.EQ, True), _condition("second", Operator.EQ, True)]
    )
    outcome = evaluate_criterion(group, _inputs_for(first, second), {})
    assert outcome.value is expected


@pytest.mark.parametrize(("first", "second", "expected"), ANY_CASES)
def test_any_truth_table(first: bool | None, second: bool | None, expected: bool | None) -> None:
    """Combine any branches with Kleene OR."""
    group = LogicGroup(
        any=[_condition("first", Operator.EQ, True), _condition("second", Operator.EQ, True)]
    )
    outcome = evaluate_criterion(group, _inputs_for(first, second), {})
    assert outcome.value is expected


@pytest.mark.parametrize(("value", "expected"), NOT_CASES)
def test_not_truth_table(value: bool | None, expected: bool | None) -> None:
    """Negate branches with Kleene NOT."""
    group = LogicGroup.model_validate({"not": {"field": "first", "op": "eq", "value": True}})
    answers = {} if value is None else {"first": answered(value)}
    outcome = evaluate_criterion(group, answers, {})
    assert outcome.value is expected


def test_decisive_fields_track_true_branches() -> None:
    """Record decisive fields from true branches only."""
    group = LogicGroup(
        any=[_condition("first", Operator.EQ, True), _condition("second", Operator.EQ, True)]
    )
    both_true = evaluate_criterion(group, _inputs_for(True, True), {})
    assert both_true.decisive == frozenset({"first", "second"})
    one_true = evaluate_criterion(group, _inputs_for(True, False), {})
    assert one_true.decisive == frozenset({"first"})
    satisfied_not = LogicGroup.model_validate(
        {"not": {"field": "first", "op": "eq", "value": True}}
    )
    negated = evaluate_criterion(satisfied_not, _inputs_for(False, None), {})
    assert negated.value is True
    assert negated.decisive == frozenset({"first"})
    unknown = evaluate_criterion(group, _inputs_for(None, None), {})
    assert unknown.decisive == frozenset()
