"""Load and validate versioned rule files (fail fast with clear errors)."""

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from app.core.enums import Route
from app.rules_engine.evaluator import DERIVED_FIELDS
from app.rules_engine.models import (
    Condition,
    Criterion,
    FlagsFile,
    FlagRule,
    Operator,
    ParamDef,
    ParamsFile,
    RedFlagRule,
    RedFlagsFile,
    RouteDef,
    RoutesFile,
    RuleSet,
)

RuleFileT = TypeVar("RuleFileT", bound=BaseModel)


class RulesLoadError(Exception):
    """Rule files are missing, malformed or inconsistent."""


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read and parse one YAML mapping file.

    Args:
        path: File to read.

    Returns:
        Parsed mapping.

    Raises:
        RulesLoadError: If the file is missing, malformed or not a mapping.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RulesLoadError(f"Cannot read rule file {path}: {exc.strerror}.") from exc
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesLoadError(f"Invalid YAML in {path}: {exc}.") from exc
    if not isinstance(raw, dict):
        raise RulesLoadError(f"Rule file {path} must hold a mapping.")
    return raw


def _load_file(path: Path, model: type[RuleFileT]) -> RuleFileT:
    """Validate one rule file against its envelope model.

    Args:
        path: File to load.
        model: Pydantic envelope model.

    Returns:
        Validated envelope.

    Raises:
        RulesLoadError: If validation fails.
    """
    try:
        return model.model_validate(_read_yaml(path))
    except ValidationError as exc:
        raise RulesLoadError(f"Invalid rule file {path}: {exc}.") from exc


def _check_version(path: Path, declared: str, expected: str) -> None:
    """Reject files whose inner version disagrees with the file name.

    Args:
        path: File being loaded.
        declared: Version declared inside the file.
        expected: Version requested by the caller.

    Raises:
        RulesLoadError: On version mismatch.
    """
    if declared != expected:
        raise RulesLoadError(
            f"Rule file {path} declares version {declared!r}, expected {expected!r}."
        )


def _check_routes(routes: list[RouteDef]) -> None:
    """Validate route table completeness and uniqueness.

    Args:
        routes: Route definitions from the routes file.

    Raises:
        RulesLoadError: On duplicates, gaps or missing review markers.
    """
    seen_ids: set[Route] = set()
    seen_precedence: set[int] = set()
    for route in routes:
        if route.id in seen_ids:
            raise RulesLoadError(f"Duplicate route id {route.id.value}.")
        if route.precedence in seen_precedence:
            raise RulesLoadError(f"Duplicate precedence {route.precedence}.")
        if not route.needs_native_review:
            raise RulesLoadError(f"Route {route.id.value} must keep needs_native_review.")
        seen_ids.add(route.id)
        seen_precedence.add(route.precedence)
    missing = sorted(route.value for route in set(Route) - seen_ids)
    if missing:
        raise RulesLoadError(f"Route table misses routes: {missing}.")


def _check_params(params: Mapping[str, ParamDef]) -> None:
    """Reject params that are not marked for clinical validation.

    Args:
        params: Parameters by name.

    Raises:
        RulesLoadError: If any param lacks the validation marker.
    """
    for name, param in params.items():
        if not param.requires_clinical_validation:
            raise RulesLoadError(f"Param {name} must keep requires_clinical_validation.")


def _check_honesty(rule_id: str, clinical: bool, native: bool) -> None:
    """Reject rules that drop the honesty markers.

    Args:
        rule_id: Rule being checked.
        clinical: Requires-clinical-validation marker.
        native: Needs-native-review marker.

    Raises:
        RulesLoadError: If either marker is false.
    """
    if not clinical:
        raise RulesLoadError(f"Rule {rule_id} must keep requires_clinical_validation.")
    if not native:
        raise RulesLoadError(f"Rule {rule_id} must keep needs_native_review.")


def _criterion_fields(criterion: Criterion) -> set[str]:
    """Collect field names referenced in one criterion tree.

    Args:
        criterion: Criterion to walk.

    Returns:
        Referenced field names.
    """
    if isinstance(criterion, Condition):
        return {criterion.field}
    fields: set[str] = set()
    if criterion.all is not None:
        for item in criterion.all:
            fields |= _criterion_fields(item)
    if criterion.any is not None:
        for item in criterion.any:
            fields |= _criterion_fields(item)
    if criterion.negation is not None:
        fields |= _criterion_fields(criterion.negation)
    return fields


def _resolve_condition(
    condition: Condition, params: Mapping[str, ParamDef], rule_id: str
) -> Condition:
    """Resolve one condition's param reference, if any.

    Args:
        condition: Condition to resolve.
        params: Parameters by name.
        rule_id: Rule being resolved (for error messages).

    Returns:
        Condition with the param value baked in.

    Raises:
        RulesLoadError: On unknown params or type mismatches.
    """
    if condition.param is None:
        return condition
    param = params.get(condition.param)
    if param is None:
        raise RulesLoadError(f"Rule {rule_id} references unknown param {condition.param!r}.")
    if condition.op in (Operator.GTE, Operator.LTE, Operator.GT, Operator.LT):
        if isinstance(param.value, bool) or not isinstance(param.value, (int, float)):
            raise RulesLoadError(
                f"Rule {rule_id} uses non-numeric param {condition.param!r} "
                f"with {condition.op.value}."
            )
    return condition.model_copy(update={"value": param.value})


def _resolve_criterion(
    criterion: Criterion, params: Mapping[str, ParamDef], rule_id: str
) -> Criterion:
    """Resolve param references inside one criterion tree.

    Args:
        criterion: Criterion to resolve.
        params: Parameters by name.
        rule_id: Rule being resolved (for error messages).

    Returns:
        Criterion with param values baked in.

    Raises:
        RulesLoadError: On unknown params, type mismatches or empty groups.
    """
    if isinstance(criterion, Condition):
        return _resolve_condition(criterion, params, rule_id)
    if criterion.all is not None:
        resolved = [_resolve_criterion(item, params, rule_id) for item in criterion.all]
        return criterion.model_copy(update={"all": resolved})
    if criterion.any is not None:
        resolved = [_resolve_criterion(item, params, rule_id) for item in criterion.any]
        return criterion.model_copy(update={"any": resolved})
    if criterion.negation is None:
        raise RulesLoadError(f"Rule {rule_id} holds an empty logic group.")
    resolved_one = _resolve_criterion(criterion.negation, params, rule_id)
    return criterion.model_copy(update={"negation": resolved_one})


def _check_required_fields(rule_id: str, required: list[str]) -> None:
    """Reject derived or duplicated required fields.

    Args:
        rule_id: Rule being checked.
        required: Declared required fields.

    Raises:
        RulesLoadError: On derived or duplicated entries.
    """
    for field in required:
        if field in DERIVED_FIELDS:
            raise RulesLoadError(f"Rule {rule_id} lists derived field {field!r} as required.")
    if len(set(required)) != len(required):
        raise RulesLoadError(f"Rule {rule_id} lists duplicated required fields.")


def _check_coverage(rule_id: str, criterion: Criterion, required: list[str]) -> None:
    """Reject criteria using fields outside required_fields.

    Args:
        rule_id: Rule being checked.
        criterion: Presence logic to walk.
        required: Declared required fields.

    Raises:
        RulesLoadError: When referenced fields are not covered.
    """
    uncovered = _criterion_fields(criterion) - set(required) - set(DERIVED_FIELDS)
    if uncovered:
        raise RulesLoadError(
            f"Rule {rule_id} uses fields outside required_fields: {sorted(uncovered)}."
        )


def _resolve_flag(rule: FlagRule, params: Mapping[str, ParamDef]) -> FlagRule:
    """Validate one flag and resolve its params.

    Args:
        rule: Flag definition.
        params: Parameters by name.

    Returns:
        Flag with param values baked into its presence logic.

    Raises:
        RulesLoadError: On any inconsistency.
    """
    _check_honesty(rule.id, rule.requires_clinical_validation, rule.needs_native_review)
    if rule.suggests_route == Route.FERTILITY_SERVICES and not rule.is_ttc_criterion:
        raise RulesLoadError(
            f"Flag {rule.id} suggests FERTILITY_SERVICES without being a TTC criterion."
        )
    _check_required_fields(rule.id, rule.required_fields)
    _check_coverage(rule.id, rule.present_when, rule.required_fields)
    resolved = _resolve_criterion(rule.present_when, params, rule.id)
    return rule.model_copy(update={"present_when": resolved})


def _resolve_red_flag(rule: RedFlagRule, params: Mapping[str, ParamDef]) -> RedFlagRule:
    """Validate one red flag and resolve its params.

    Args:
        rule: Red flag definition.
        params: Parameters by name.

    Returns:
        Red flag with param values baked into its presence logic.

    Raises:
        RulesLoadError: On any inconsistency.
    """
    _check_honesty(rule.id, rule.requires_clinical_validation, rule.needs_native_review)
    _check_required_fields(rule.id, rule.required_fields)
    _check_coverage(rule.id, rule.present_when, rule.required_fields)
    resolved = _resolve_criterion(rule.present_when, params, rule.id)
    return rule.model_copy(update={"present_when": resolved})


@lru_cache(maxsize=8)
def load_rules(rules_dir: Path, version: str) -> RuleSet:
    """Load one versioned rule set from a directory.

    Results are cached by directory and version; the application warms the
    cache at startup so invalid rules fail fast before serving traffic.

    Args:
        rules_dir: Directory holding the versioned YAML files.
        version: Rule version to load (for example ``0.1``).

    Returns:
        Validated rule set with params resolved into conditions.

    Raises:
        RulesLoadError: If any file is missing or invalid.
    """
    flags_path = rules_dir / f"flags.v{version}.yaml"
    redflags_path = rules_dir / f"redflags.v{version}.yaml"
    routes_path = rules_dir / f"routes.v{version}.yaml"
    params_path = rules_dir / f"params.v{version}.yaml"
    flags_file = _load_file(flags_path, FlagsFile)
    redflags_file = _load_file(redflags_path, RedFlagsFile)
    routes_file = _load_file(routes_path, RoutesFile)
    params_file = _load_file(params_path, ParamsFile)
    _check_version(flags_path, flags_file.version, version)
    _check_version(redflags_path, redflags_file.version, version)
    _check_version(routes_path, routes_file.version, version)
    _check_version(params_path, params_file.version, version)
    _check_routes(routes_file.routes)
    _check_params(params_file.params)
    seen_ids: set[str] = set()
    for rule_id in [rule.id for rule in flags_file.flags] + [
        rule.id for rule in redflags_file.redflags
    ]:
        if rule_id in seen_ids:
            raise RulesLoadError(f"Duplicate rule id {rule_id}.")
        seen_ids.add(rule_id)
    flags = tuple(_resolve_flag(rule, params_file.params) for rule in flags_file.flags)
    red_flags = tuple(
        _resolve_red_flag(rule, params_file.params) for rule in redflags_file.redflags
    )
    return RuleSet(
        version=version,
        flags=flags,
        red_flags=red_flags,
        routes=tuple(routes_file.routes),
        params=dict(params_file.params),
    )
