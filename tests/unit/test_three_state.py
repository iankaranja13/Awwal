"""Three-state flag logic and derived-field behaviour."""

from app.core.enums import FlagState, ItemStatus
from app.rules_engine import RuleSet, run_triage
from app.rules_engine.evaluator import compute_bmi
from tests.unit.rule_helpers import answered, assessment, declined, skipped, unsure


def test_present_wins_over_other_missing(ruleset: RuleSet) -> None:
    """Keep flags present when other required fields are missing."""
    inputs = assessment(testicular_torsion=answered(True))
    result = run_triage(ruleset, inputs)
    states = {flag.id: flag.state for flag in result.flags}
    assert states["HX_TORSION_INJURY_SURGERY"] == FlagState.PRESENT
    present = [flag for flag in result.flags if flag.id == "HX_TORSION_INJURY_SURGERY"][0]
    assert present.reason_fields == ["testicular_torsion"]
    assert present.missing_fields == []


def test_missing_required_is_not_assessable(ruleset: RuleSet) -> None:
    """Mark flags not assessable when required items are missing."""
    inputs = assessment(testicular_torsion=answered(False))
    result = run_triage(ruleset, inputs)
    states = {flag.id: flag.state for flag in result.flags}
    assert states["HX_TORSION_INJURY_SURGERY"] == FlagState.NOT_ASSESSABLE
    missing = [flag for flag in result.flags if flag.id == "HX_TORSION_INJURY_SURGERY"][0]
    assert missing.missing_fields == ["testicular_injury_or_surgery"]
    assert missing.reason_fields == []


def test_non_answer_statuses_are_not_assessable(ruleset: RuleSet) -> None:
    """Treat skipped, unsure and declined answers as missing."""
    builders = {"skipped": skipped(), "unsure": unsure(), "declined": declined()}
    for name, answer in builders.items():
        inputs = assessment(undescended_testis=answer)
        result = run_triage(ruleset, inputs)
        states = {flag.id: flag.state for flag in result.flags}
        assert states["HX_UNDESCENDED_TESTIS"] == FlagState.NOT_ASSESSABLE, name


def test_missing_key_matches_skipped(ruleset: RuleSet) -> None:
    """Treat an absent key exactly like a skipped answer."""
    states_missing = run_triage(ruleset, assessment()).flags
    states_skipped = run_triage(ruleset, assessment(undescended_testis=skipped())).flags
    by_id_missing = {flag.id: flag.state for flag in states_missing}
    by_id_skipped = {flag.id: flag.state for flag in states_skipped}
    assert by_id_missing["HX_UNDESCENDED_TESTIS"] == by_id_skipped["HX_UNDESCENDED_TESTIS"]
    assert by_id_missing["HX_UNDESCENDED_TESTIS"] == FlagState.NOT_ASSESSABLE


def test_answered_negative_is_not_present(ruleset: RuleSet) -> None:
    """Mark fully answered negative flags as not present."""
    inputs = assessment(
        testicular_torsion=answered(False), testicular_injury_or_surgery=answered(False)
    )
    result = run_triage(ruleset, inputs)
    states = {flag.id: flag.state for flag in result.flags}
    assert states["HX_TORSION_INJURY_SURGERY"] == FlagState.NOT_PRESENT_FROM_PROVIDED_DATA


def test_false_condition_with_answered_required_is_not_present(ruleset: RuleSet) -> None:
    """Mark unmet but fully answered criteria as not present."""
    inputs = assessment(trying_to_conceive=answered("yes"), months_trying=answered(3))
    result = run_triage(ruleset, inputs)
    states = {flag.id: flag.state for flag in result.flags}
    assert states["LS_TTC_STANDARD"] == FlagState.NOT_PRESENT_FROM_PROVIDED_DATA


def test_bmi_computes_from_height_and_weight() -> None:
    """Compute BMI only from answered positive measurements."""
    assert compute_bmi({"height_cm": answered(178), "weight_kg": answered(70)}) == 22.1
    assert compute_bmi({"height_cm": answered(178)}) is None
    assert compute_bmi({"weight_kg": answered(70)}) is None
    assert compute_bmi({"height_cm": answered(0), "weight_kg": answered(70)}) is None
    assert compute_bmi({"height_cm": answered(178), "weight_kg": answered(-5)}) is None
    assert compute_bmi({"height_cm": answered("tall"), "weight_kg": answered(70)}) is None


def test_bmi_flag_fires_at_threshold(ruleset: RuleSet) -> None:
    """Fire the BMI flag at or above the threshold only."""
    at_threshold = assessment(height_cm=answered(200), weight_kg=answered(100))
    states = {flag.id: flag.state for flag in run_triage(ruleset, at_threshold).flags}
    assert states["MB_BMI"] == FlagState.PRESENT
    below = assessment(height_cm=answered(200), weight_kg=answered(99))
    states = {flag.id: flag.state for flag in run_triage(ruleset, below).flags}
    assert states["MB_BMI"] == FlagState.NOT_PRESENT_FROM_PROVIDED_DATA


def test_bmi_rounding_applies_before_comparison(ruleset: RuleSet) -> None:
    """Compare the rounded BMI so stored and compared values agree."""
    inputs = assessment(height_cm=answered(250), weight_kg=answered(156))
    result = run_triage(ruleset, inputs)
    assert result.derived_values == {"bmi": 25.0}
    states = {flag.id: flag.state for flag in result.flags}
    assert states["MB_BMI"] == FlagState.PRESENT


def test_bmi_missing_height_is_not_assessable(ruleset: RuleSet) -> None:
    """Mark the BMI flag not assessable without both measurements."""
    inputs = assessment(weight_kg=answered(70))
    result = run_triage(ruleset, inputs)
    flag = [item for item in result.flags if item.id == "MB_BMI"][0]
    assert flag.state == FlagState.NOT_ASSESSABLE
    assert flag.missing_fields == ["height_cm"]


def test_status_names_match_contract() -> None:
    """Expose the exact status and state names from the contract."""
    assert {state.value for state in FlagState} == {
        "PRESENT",
        "NOT_PRESENT_FROM_PROVIDED_DATA",
        "NOT_ASSESSABLE",
    }
    assert {status.value for status in ItemStatus} == {
        "answered",
        "skipped",
        "unsure",
        "prefer_not_to_say",
    }
