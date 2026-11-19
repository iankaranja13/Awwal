"""Rule loader validation behaviour."""

from pathlib import Path

import pytest

from app.rules_engine import RuleSet, load_rules
from app.rules_engine.loader import RulesLoadError
from app.rules_engine.models import Condition
from tests.unit.rule_helpers import REAL_RULES_DIR

NAMES = ["flags.v0.1.yaml", "redflags.v0.1.yaml", "routes.v0.1.yaml", "params.v0.1.yaml"]


def _real_text(name: str) -> str:
    return (REAL_RULES_DIR / name).read_text(encoding="utf-8")


def _rules_dir(tmp_path: Path, **overrides: str) -> Path:
    """Copy real rule files, overriding given names with new text."""
    target = tmp_path / "rules"
    target.mkdir()
    for name in NAMES:
        (target / name).write_text(overrides.get(name, _real_text(name)), encoding="utf-8")
    return target


def test_loads_real_rules(ruleset: RuleSet) -> None:
    """Load the shipped rule files with expected counts."""
    assert ruleset.version == "0.1"
    assert len(ruleset.flags) == 24
    assert len(ruleset.red_flags) == 5
    assert len(ruleset.routes) == 6
    assert set(ruleset.params) == {
        "ttc_threshold_months",
        "ttc_threshold_months_older_partner",
        "older_partner_band",
        "bmi_flag_at_or_above",
    }


def test_params_resolve_into_conditions(ruleset: RuleSet) -> None:
    """Bake param values into conditions while keeping the param name."""
    by_id = {rule.id: rule for rule in ruleset.flags}
    ttc_group = by_id["LS_TTC_STANDARD"].present_when
    assert not isinstance(ttc_group, Condition)
    assert ttc_group.all is not None
    months_condition = ttc_group.all[1]
    assert isinstance(months_condition, Condition)
    assert months_condition.param == "ttc_threshold_months"
    assert months_condition.value == 12
    bmi_condition = by_id["MB_BMI"].present_when
    assert isinstance(bmi_condition, Condition)
    assert bmi_condition.param == "bmi_flag_at_or_above"
    assert bmi_condition.value == 25.0


def test_missing_directory_fails(tmp_path: Path) -> None:
    """Fail fast when the rules directory has no rule files."""
    with pytest.raises(RulesLoadError, match="Cannot read rule file"):
        load_rules(tmp_path / "absent", "0.1")


def test_invalid_yaml_fails(tmp_path: Path) -> None:
    """Fail fast on malformed YAML."""
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": "flags:\n  - id: [unclosed"})
    with pytest.raises(RulesLoadError, match="Invalid YAML"):
        load_rules(rules_dir, "0.1")


def test_non_mapping_yaml_fails(tmp_path: Path) -> None:
    """Fail fast when a rule file holds no mapping."""
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": "- just\n- a\n- list\n"})
    with pytest.raises(RulesLoadError, match="must hold a mapping"):
        load_rules(rules_dir, "0.1")


def test_version_mismatch_fails(tmp_path: Path) -> None:
    """Fail fast when the inner version disagrees with the file name."""
    text = _real_text("flags.v0.1.yaml").replace('version: "0.1"', 'version: "0.2"')
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="declares version"):
        load_rules(rules_dir, "0.1")


def test_unknown_operator_fails(tmp_path: Path) -> None:
    """Fail fast on an unknown operator."""
    text = _real_text("flags.v0.1.yaml").replace("op: eq", "op: bogus", 1)
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Invalid rule file"):
        load_rules(rules_dir, "0.1")


def test_unknown_route_fails(tmp_path: Path) -> None:
    """Fail fast on an unknown suggested route."""
    text = _real_text("flags.v0.1.yaml").replace(
        "suggests_route: PRIMARY_CARE", "suggests_route: NOWHERE", 1
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Invalid rule file"):
        load_rules(rules_dir, "0.1")


def test_uncovered_field_fails(tmp_path: Path) -> None:
    """Fail fast when presence logic uses undeclared fields."""
    text = _real_text("flags.v0.1.yaml").replace(
        "present_when: {field: undescended_testis", "present_when: {field: something_else", 1
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="outside required_fields"):
        load_rules(rules_dir, "0.1")


def test_unknown_param_fails(tmp_path: Path) -> None:
    """Fail fast on references to missing params."""
    text = _real_text("flags.v0.1.yaml").replace(
        "param: ttc_threshold_months}", "param: nope}", 1
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="unknown param"):
        load_rules(rules_dir, "0.1")


def test_value_and_param_together_fail(tmp_path: Path) -> None:
    """Fail fast when a condition sets both value and param."""
    text = _real_text("flags.v0.1.yaml").replace(
        "{field: months_trying, op: gte, param: ttc_threshold_months}",
        "{field: months_trying, op: gte, param: ttc_threshold_months, value: 12}",
        1,
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Invalid rule file"):
        load_rules(rules_dir, "0.1")


def test_exists_with_value_fails(tmp_path: Path) -> None:
    """Fail fast when exists takes a value."""
    text = _real_text("flags.v0.1.yaml").replace(
        "{field: undescended_testis, op: eq, value: true}",
        "{field: undescended_testis, op: exists, value: true}",
        1,
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Invalid rule file"):
        load_rules(rules_dir, "0.1")


def test_non_ttc_fertility_suggestion_fails(tmp_path: Path) -> None:
    """Fail fast when a non-TTC flag suggests fertility services."""
    text = _real_text("flags.v0.1.yaml").replace(
        "suggests_route: PRIMARY_CARE", "suggests_route: FERTILITY_SERVICES", 1
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="without being a TTC criterion"):
        load_rules(rules_dir, "0.1")


def test_duplicate_ids_fail(tmp_path: Path) -> None:
    """Fail fast on duplicated rule ids."""
    text = _real_text("flags.v0.1.yaml").replace("id: HX_STI", "id: HX_MUMPS", 1)
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Duplicate rule id"):
        load_rules(rules_dir, "0.1")


def test_unmarked_clinical_validation_fails(tmp_path: Path) -> None:
    """Fail fast when a rule drops the validation marker."""
    text = _real_text("flags.v0.1.yaml").replace(
        "requires_clinical_validation: true", "requires_clinical_validation: false", 1
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="requires_clinical_validation"):
        load_rules(rules_dir, "0.1")


def test_duplicate_precedence_fails(tmp_path: Path) -> None:
    """Fail fast on duplicated route precedence."""
    text = _real_text("routes.v0.1.yaml").replace("precedence: 400", "precedence: 500", 1)
    rules_dir = _rules_dir(tmp_path, **{"routes.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Duplicate precedence"):
        load_rules(rules_dir, "0.1")


def test_missing_route_fails(tmp_path: Path) -> None:
    """Fail fast when the route table is incomplete."""
    text = _real_text("routes.v0.1.yaml").split("  - id: SELF_CARE\n")[0]
    rules_dir = _rules_dir(tmp_path, **{"routes.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="misses routes"):
        load_rules(rules_dir, "0.1")


def test_scalar_in_value_fails(tmp_path: Path) -> None:
    """Fail fast when in takes a scalar value."""
    text = _real_text("flags.v0.1.yaml").replace(
        'value: ["former", "current"]', 'value: "current"', 1
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Invalid rule file"):
        load_rules(rules_dir, "0.1")


def test_string_ordered_value_fails(tmp_path: Path) -> None:
    """Fail fast when an ordering comparison takes a string."""
    text = _real_text("flags.v0.1.yaml").replace(
        "{field: bmi, op: gte, param: bmi_flag_at_or_above}",
        '{field: bmi, op: gte, value: "high"}',
        1,
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="Invalid rule file"):
        load_rules(rules_dir, "0.1")


def test_non_numeric_param_fails(tmp_path: Path) -> None:
    """Fail fast when an ordering param is not numeric."""
    text = _real_text("params.v0.1.yaml").replace("value: 25.0", 'value: "high"', 1)
    rules_dir = _rules_dir(tmp_path, **{"params.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="non-numeric param"):
        load_rules(rules_dir, "0.1")


def test_derived_required_field_fails(tmp_path: Path) -> None:
    """Fail fast when required_fields names a derived field."""
    text = _real_text("flags.v0.1.yaml").replace(
        "required_fields: [height_cm, weight_kg]",
        "required_fields: [height_cm, weight_kg, bmi]",
        1,
    )
    rules_dir = _rules_dir(tmp_path, **{"flags.v0.1.yaml": text})
    with pytest.raises(RulesLoadError, match="derived field"):
        load_rules(rules_dir, "0.1")
