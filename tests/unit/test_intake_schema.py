"""Intake schema serving, validation and rules consistency."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.enums import ItemStatus, ItemType
from app.core.errors import InvalidInputError
from app.rules_engine import RuleSet
from app.rules_engine.models import Condition, Criterion, Label
from app.schemas.intake import AnswerIn, IntakeItem, IntakeSchemaDocument, ItemOption
from app.services.intake import IntakeSchemaError, load_intake_schema, validate_answers
from tests.unit.rule_helpers import APP_CONTENT_DIR


def test_schema_served_bilingually(db_client: TestClient, auth_headers: dict[str, str]) -> None:
    """Serve all schema items with English and Arabic text."""
    response = db_client.get("/api/v1/intake/schema", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "0.1"
    assert len(body["items"]) == 35
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["diabetes"]["label"]["en"]
    assert by_id["diabetes"]["label"]["ar"]
    assert by_id["diabetes"]["why_we_ask"]["en"]
    assert by_id["diabetes"]["why_we_ask"]["ar"]
    options = by_id["tobacco_vaping_shisha"]["options"]
    assert [option["value"] for option in options] == ["never", "former", "current"]
    assert all(option["label"]["en"] and option["label"]["ar"] for option in options)


def test_schema_requires_authentication(db_client: TestClient) -> None:
    """Reject anonymous schema reads."""
    assert db_client.get("/api/v1/intake/schema").status_code == 401


def _write_schema(tmp_path: Path, items: list[dict[str, Any]]) -> str:
    content = tmp_path / "content"
    content.mkdir()
    (content / "intake_schema.json").write_text(
        json.dumps({"schema_version": "0.1", "items": items}), encoding="utf-8"
    )
    return str(content)


def _item(item_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": item_id,
        "domain": "context",
        "type": "boolean",
        "required_for_flags": [],
        "label": {"en": "Label", "ar": "تسمية"},
        "why_we_ask": {"en": "Why", "ar": "لماذا"},
        "sensitive": True,
        "optional_by_design": False,
        "needs_native_review": True,
    }
    base.update(overrides)
    return base


def test_missing_schema_fails(tmp_path: Path) -> None:
    """Fail fast when the schema file is missing."""
    with pytest.raises(IntakeSchemaError, match="Cannot read intake schema"):
        load_intake_schema(str(tmp_path / "absent"))


def test_invalid_schema_json_fails(tmp_path: Path) -> None:
    """Fail fast on malformed schema JSON."""
    content = tmp_path / "content"
    content.mkdir()
    (content / "intake_schema.json").write_text("{oops", encoding="utf-8")
    with pytest.raises(IntakeSchemaError, match="Invalid JSON"):
        load_intake_schema(str(content))


def test_duplicate_item_ids_fail(tmp_path: Path) -> None:
    """Fail fast on duplicated item ids."""
    content_dir = _write_schema(tmp_path, [_item("dup"), _item("dup")])
    with pytest.raises(IntakeSchemaError, match="Duplicate intake item id"):
        load_intake_schema(content_dir)


def test_choice_without_options_fails(tmp_path: Path) -> None:
    """Fail fast when a choice item has no options."""
    content_dir = _write_schema(tmp_path, [_item("pick", type="single_choice")])
    with pytest.raises(IntakeSchemaError, match="needs options"):
        load_intake_schema(content_dir)


def test_unmarked_review_fails(tmp_path: Path) -> None:
    """Fail fast when an item drops the review marker."""
    content_dir = _write_schema(tmp_path, [_item("pick", needs_native_review=False)])
    with pytest.raises(IntakeSchemaError, match="needs_native_review"):
        load_intake_schema(content_dir)


def _multi_schema() -> IntakeSchemaDocument:
    label = Label(en="Label", ar="تسمية")
    options = [ItemOption(value="a", label=label), ItemOption(value="b", label=label)]
    return IntakeSchemaDocument(
        schema_version="test",
        items=[
            IntakeItem(
                id="multi",
                domain="test",
                type=ItemType.MULTI_CHOICE,
                label=label,
                why_we_ask=label,
                options=options,
                sensitive=False,
                optional_by_design=False,
                needs_native_review=True,
            ),
            IntakeItem(
                id="note",
                domain="test",
                type=ItemType.TEXT,
                label=label,
                why_we_ask=label,
                sensitive=False,
                optional_by_design=False,
                needs_native_review=True,
            ),
        ],
    )


def test_multi_choice_validation() -> None:
    """Validate multi-choice answers against their options."""
    schema = _multi_schema()
    ok = validate_answers(schema, {"multi": AnswerIn(value=["a", "b"], status=ItemStatus.ANSWERED)})
    assert ok["multi"]["value"] == ["a", "b"]
    for bad in (["zzz"], [], "a"):
        with pytest.raises(InvalidInputError):
            validate_answers(schema, {"multi": AnswerIn(value=bad, status=ItemStatus.ANSWERED)})


def test_text_default_length_cap() -> None:
    """Bound text items without an explicit cap."""
    schema = _multi_schema()
    validate_answers(schema, {"note": AnswerIn(value="x" * 5000, status=ItemStatus.ANSWERED)})
    with pytest.raises(InvalidInputError):
        validate_answers(schema, {"note": AnswerIn(value="x" * 5001, status=ItemStatus.ANSWERED)})


def _conditions(criterion: Criterion) -> list[Condition]:
    if isinstance(criterion, Condition):
        return [criterion]
    found: list[Condition] = []
    group = criterion
    for branch in (group.all or [], group.any or []):
        for item in branch:
            found.extend(_conditions(item))
    if group.negation is not None:
        found.extend(_conditions(group.negation))
    return found


def test_schema_covers_rule_fields(ruleset: RuleSet) -> None:
    """Keep every rule field present in the intake schema."""
    schema = load_intake_schema(str(APP_CONTENT_DIR))
    item_ids = {item.id for item in schema.items}
    for rule in list(ruleset.flags) + list(ruleset.red_flags):
        for field in rule.required_fields:
            assert field in item_ids, rule.id
        for condition in _conditions(rule.present_when):
            if condition.field != "bmi":
                assert condition.field in item_ids, rule.id


def test_schema_flag_references_exist(ruleset: RuleSet) -> None:
    """Keep every schema flag reference pointing at a real rule."""
    schema = load_intake_schema(str(APP_CONTENT_DIR))
    rule_ids = {rule.id for rule in ruleset.flags} | {rule.id for rule in ruleset.red_flags}
    for item in schema.items:
        for flag_id in item.required_for_flags:
            assert flag_id in rule_ids, item.id


def test_rule_values_match_choice_options(ruleset: RuleSet) -> None:
    """Keep rule literals and params inside schema option values."""
    schema = load_intake_schema(str(APP_CONTENT_DIR))
    options = {
        item.id: [option.value for option in item.options]
        for item in schema.items
        if item.type == ItemType.SINGLE_CHOICE
    }
    for rule in list(ruleset.flags) + list(ruleset.red_flags):
        for condition in _conditions(rule.present_when):
            if condition.field not in options:
                continue
            values = condition.value if isinstance(condition.value, list) else [condition.value]
            for value in values:
                assert value in options[condition.field], (rule.id, condition.field, value)
