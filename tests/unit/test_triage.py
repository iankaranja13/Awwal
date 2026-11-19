"""Triage route selection and monotonicity behaviour."""

import random
from typing import Any

import pytest

from app.core.enums import FlagState, Route
from app.rules_engine import RuleSet, run_triage
from app.rules_engine.models import AssessmentInput
from tests.unit.rule_helpers import answered, assessment, clean_answers

TRIGGER_VALUES: dict[str, Any] = {
    "undescended_testis": True,
    "testicular_torsion": True,
    "testicular_injury_or_surgery": True,
    "hernia_or_genital_surgery": True,
    "known_varicocele": True,
    "genital_infection_or_inflammation": True,
    "sti_history": True,
    "mumps_testicular_inflammation": True,
    "diabetes": True,
    "high_blood_pressure": True,
    "high_cholesterol": True,
    "tobacco_vaping_shisha": "current",
    "alcohol_use": "regular",
    "anabolic_steroids_or_testosterone": "current",
    "other_substances": "current",
    "occupational_heat_or_chemicals": True,
    "chemotherapy_or_radiation": True,
    "chronic_conditions": True,
    "low_desire_or_sexual_function_change": True,
    "erectile_or_ejaculation_difficulty": True,
    "prior_semen_analysis_result": "abnormal",
    "prior_hormone_result": "abnormal",
    "family_history_infertility_or_genetic": True,
    "trying_to_conceive": "yes",
    "months_trying": 14,
    "testicular_pain_sudden_severe": True,
    "testicular_lump": True,
    "testicular_swelling": True,
    "fever_with_testicular_pain": True,
    "blood_in_semen": True,
}

RED_FLAG_MESSAGES = {
    "testicular_pain_sudden_severe": "SAFETY_URGENT_PAIN",
    "testicular_lump": "SAFETY_URGENT_LUMP",
    "testicular_swelling": "SAFETY_URGENT_SWELLING",
    "fever_with_testicular_pain": "SAFETY_URGENT_FEVER_PAIN",
    "blood_in_semen": "SAFETY_URGENT_BLOOD",
}


def test_clean_answers_route_self_care(ruleset: RuleSet) -> None:
    """Route fully negative answers to plain self-care."""
    result = run_triage(ruleset, AssessmentInput(answers=clean_answers(ruleset)))
    assert result.urgent is False
    assert result.route == Route.SELF_CARE
    assert result.route_reason == []
    assert result.missing_items == []
    assert result.static_message_id is None
    assert {flag.state for flag in result.flags} == {FlagState.NOT_PRESENT_FROM_PROVIDED_DATA}
    assert all(not red.present for red in result.red_flags)


@pytest.mark.parametrize(("item", "message"), sorted(RED_FLAG_MESSAGES.items()))
def test_each_red_flag_routes_urgent(ruleset: RuleSet, item: str, message: str) -> None:
    """Route every red flag to urgent with its static message."""
    answers = clean_answers(ruleset)
    answers[item] = answered(True)
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.urgent is True
    assert result.route == Route.URGENT
    assert result.static_message_id == message
    assert result.flags == []
    assert len(result.red_flags_present) == 1


def test_red_flag_short_circuits_flag_evaluation(ruleset: RuleSet) -> None:
    """Skip flag evaluation entirely when a red flag is present."""
    answers = clean_answers(ruleset)
    answers["testicular_lump"] = answered(True)
    answers["undescended_testis"] = answered(True)
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.URGENT
    assert result.flags == []
    assert result.route_reason == ["RF_TESTICULAR_LUMP"]


def test_multiple_red_flags_use_file_order(ruleset: RuleSet) -> None:
    """Pick the first file-order message when several red flags are present."""
    answers = clean_answers(ruleset)
    answers["blood_in_semen"] = answered(True)
    answers["testicular_pain_sudden_severe"] = answered(True)
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.URGENT
    assert result.static_message_id == "SAFETY_URGENT_PAIN"
    assert result.route_reason == ["RF_SUDDEN_SEVERE_TESTICULAR_PAIN", "RF_BLOOD_IN_SEMEN"]


def test_precedence_prefers_specialist_over_primary(ruleset: RuleSet) -> None:
    """Select the highest-precedence suggested route."""
    result = run_triage(
        ruleset,
        assessment(known_varicocele=answered(True), diabetes=answered(True)),
    )
    assert result.route == Route.ANDROLOGY_UROLOGY
    assert result.route_reason == ["HX_VARICOCELE"]


def test_standard_time_to_conceive_routes_fertility(ruleset: RuleSet) -> None:
    """Route the standard TTC criterion to fertility services."""
    answers = clean_answers(ruleset)
    answers["trying_to_conceive"] = answered("yes")
    answers["months_trying"] = answered(14)
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.FERTILITY_SERVICES
    assert result.route_reason == ["LS_TTC_STANDARD"]


def test_earlier_time_to_conceive_routes_fertility(ruleset: RuleSet) -> None:
    """Route the earlier TTC criterion to fertility services."""
    answers = clean_answers(ruleset)
    answers["trying_to_conceive"] = answered("yes")
    answers["months_trying"] = answered(8)
    answers["partner_age_band"] = answered("35_plus")
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.FERTILITY_SERVICES
    assert result.route_reason == ["LS_TTC_EARLIER"]


def test_specialist_beats_fertility_services(ruleset: RuleSet) -> None:
    """Prefer andrology over fertility services when both are suggested."""
    answers = clean_answers(ruleset)
    answers["trying_to_conceive"] = answered("yes")
    answers["months_trying"] = answered(14)
    answers["known_varicocele"] = answered(True)
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.ANDROLOGY_UROLOGY
    assert result.route_reason == ["HX_VARICOCELE"]


def test_missing_key_item_never_returns_plain_self_care(ruleset: RuleSet) -> None:
    """Return a provisional route when key items are missing."""
    answers = clean_answers(ruleset)
    del answers["tobacco_vaping_shisha"]
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.SELF_CARE_PROVISIONAL
    assert result.missing_items == ["tobacco_vaping_shisha"]


def test_missing_red_flag_item_forces_provisional(ruleset: RuleSet) -> None:
    """Treat unassessed red flags as key missing data."""
    answers = clean_answers(ruleset)
    del answers["blood_in_semen"]
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.SELF_CARE_PROVISIONAL
    assert result.missing_items == ["blood_in_semen"]


def test_missing_optional_items_keep_self_care(ruleset: RuleSet) -> None:
    """Ignore missing optional items for the plain self-care route."""
    answers = clean_answers(ruleset)
    del answers["family_history_infertility_or_genetic"]
    del answers["prior_hormone_result"]
    del answers["partner_age_band"]
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.SELF_CARE
    assert result.missing_items == []


def test_empty_answers_are_provisional(ruleset: RuleSet) -> None:
    """Route empty answers to provisional, never to plain self-care."""
    result = run_triage(ruleset, assessment())
    assert result.route == Route.SELF_CARE_PROVISIONAL
    assert result.missing_items != []
    assert result.route_reason == []


def test_unknown_items_are_ignored(ruleset: RuleSet) -> None:
    """Ignore answer keys that no rule references."""
    answers = clean_answers(ruleset)
    answers["unknown_future_item"] = answered(True)
    result = run_triage(ruleset, AssessmentInput(answers=answers))
    assert result.route == Route.SELF_CARE


def test_missing_non_decisive_items_never_lowers_route(ruleset: RuleSet) -> None:
    """Keep routes monotone when non-trigger answers go missing."""
    precedence = {route.id: route.precedence for route in ruleset.routes}
    rng = random.Random(20261119)
    for _ in range(200):
        base = clean_answers(ruleset)
        flipped = set()
        for item, trigger in TRIGGER_VALUES.items():
            if rng.random() < 0.15:
                base[item] = answered(trigger)
                flipped.add(item)
        before = run_triage(ruleset, AssessmentInput(answers=dict(base)))
        for item in [item for item in base if item not in flipped]:
            if rng.random() < 0.3:
                del base[item]
        after = run_triage(ruleset, AssessmentInput(answers=base))
        assert precedence[after.route] >= precedence[before.route]
        before_present = {
            flag.id for flag in before.flags if flag.state == FlagState.PRESENT
        }
        after_present = {flag.id for flag in after.flags if flag.state == FlagState.PRESENT}
        assert before_present <= after_present
