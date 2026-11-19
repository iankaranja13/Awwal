"""Builders for engine tests."""

from pathlib import Path
from typing import Any

from app.core.enums import ItemStatus
from app.rules_engine.models import AssessmentInput, ItemAnswer, RuleSet

REAL_RULES_DIR = Path(__file__).resolve().parents[2] / "rules"
APP_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "content"

_CLEAN_VALUES: dict[str, Any] = {
    "trying_to_conceive": "no",
    "months_trying": 0,
    "partner_age_band": "under_30",
    "tobacco_vaping_shisha": "never",
    "alcohol_use": "never",
    "anabolic_steroids_or_testosterone": "never",
    "other_substances": "never",
    "prior_semen_analysis_result": "normal",
    "prior_hormone_result": "normal",
    "height_cm": 178,
    "weight_kg": 70,
}


def answered(value: Any) -> ItemAnswer:
    """Build an answered item."""
    return ItemAnswer(value=value, status=ItemStatus.ANSWERED)


def skipped() -> ItemAnswer:
    """Build a skipped item."""
    return ItemAnswer(value=None, status=ItemStatus.SKIPPED)


def unsure() -> ItemAnswer:
    """Build an unsure item."""
    return ItemAnswer(value=None, status=ItemStatus.UNSURE)


def declined() -> ItemAnswer:
    """Build a prefer-not-to-say item."""
    return ItemAnswer(value=None, status=ItemStatus.PREFER_NOT_TO_SAY)


def assessment(**items: ItemAnswer) -> AssessmentInput:
    """Build an assessment input from named items."""
    return AssessmentInput(answers=dict(items))


def clean_answers(rules: RuleSet) -> dict[str, ItemAnswer]:
    """Build a fully answered negative answer set for the rule set."""
    fields = {field for rule in rules.flags for field in rule.required_fields}
    fields |= {field for rule in rules.red_flags for field in rule.required_fields}
    answers = {field: answered(_CLEAN_VALUES.get(field, False)) for field in fields}
    answers["age_band"] = answered("30_34")
    return answers
