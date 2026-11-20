"""Validation of LLM explanations and briefs (reject and fall back)."""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.core.enums import FlagState, Language, Route
from app.llm.banned_patterns import (
    REQUIRED_DISCLAIMER_GROUPS,
    find_banned,
    find_numbers,
    find_other_route,
    normalize_arabic,
)
from app.rules_engine.evaluator import compute_derived
from app.rules_engine.models import (
    AssessmentInput,
    Condition,
    Criterion,
    FlagResult,
    RuleSet,
)
from app.schemas.explain import BriefOutput, ExplainerOutput


@dataclass(frozen=True)
class ValidatorResult:
    """Validation outcome with reasons."""

    ok: bool
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialise for storage.

        Returns:
            JSON-safe mapping.
        """
        return {"ok": self.ok, "errors": list(self.errors)}


@dataclass(frozen=True)
class ValidationContext:
    """Ground truth an explanation is checked against."""

    language: Language
    route: Route
    present_flag_ids: frozenset[str] = frozenset()
    all_flag_ids: frozenset[str] = frozenset()
    not_assessable_ids: frozenset[str] = frozenset()
    allowed_numbers: frozenset[str] = frozenset()
    provided_sources: frozenset[str] = frozenset()


def _numbers_allowed(value: str, allowed: frozenset[str]) -> bool:
    """Check one number token against the allowed set.

    Args:
        value: Found number token.
        allowed: Allowed number strings.

    Returns:
        True when the token matches numerically.
    """
    if value in allowed:
        return True
    try:
        found = float(value)
    except ValueError:
        return False
    for candidate in allowed:
        try:
            if float(candidate) == found:
                return True
        except ValueError:
            continue
    return False


def _check_disclaimer(disclaimer: str, language: Language, errors: list[str]) -> None:
    """Require every disclaimer phrase group.

    Args:
        disclaimer: Disclaimer text.
        language: Expected language.
        errors: Error list to extend.
    """
    groups = REQUIRED_DISCLAIMER_GROUPS[language.value]
    if language == Language.AR:
        haystack = normalize_arabic(disclaimer)
        for group in groups:
            if not any(phrase in haystack for phrase in group):
                errors.append(f"disclaimer misses required Arabic statement {group[0]!r}")
        return
    lowered = disclaimer.lower()
    for group in groups:
        if not any(phrase in lowered for phrase in group):
            errors.append(f"disclaimer misses required statement {group[0]!r}")


def _check_numbers(texts: list[str], allowed: frozenset[str], errors: list[str]) -> None:
    """Reject numbers absent from the input.

    Args:
        texts: Texts to scan.
        allowed: Allowed number strings.
        errors: Error list to extend.
    """
    for text in texts:
        for number in find_numbers(text):
            if not _numbers_allowed(number, allowed):
                errors.append(f"number {number!r} is not present in the input")


def _check_banned(texts: list[str], language: Language, brief: bool, errors: list[str]) -> None:
    """Reject verdict, diagnosis and treatment language.

    Args:
        texts: Texts to scan.
        language: Text language.
        brief: Whether to include brief-only patterns.
        errors: Error list to extend.
    """
    for text in texts:
        for pattern in find_banned(text, language.value, brief=brief):
            errors.append(f"banned language: {pattern}")


def _criterion_params(criterion: Criterion) -> set[str]:
    """Collect param names referenced in one criterion tree.

    Args:
        criterion: Criterion to walk.

    Returns:
        Referenced param names.
    """
    if isinstance(criterion, Condition):
        return {criterion.param} if criterion.param is not None else set()
    names: set[str] = set()
    group = criterion
    for branch in list(group.all or []) + list(group.any or []):
        names |= _criterion_params(branch)
    if group.negation is not None:
        names |= _criterion_params(group.negation)
    return names


def build_allowed_numbers(
    rules: RuleSet, flags: list[FlagResult], missing_count: int, inputs: AssessmentInput
) -> frozenset[str]:
    """Collect numbers an explanation may legitimately cite.

    Args:
        rules: Loaded rule set.
        flags: Evaluated flag outcomes.
        missing_count: Missing item count.
        inputs: Assessment answers.

    Returns:
        Allowed number strings (data, used params and structural counts).
    """
    allowed: set[str] = set()
    for answer in inputs.answers.values():
        if isinstance(answer.value, bool):
            continue
        if isinstance(answer.value, (int, float)):
            allowed.add(str(answer.value))
    for value in compute_derived(inputs.answers).values():
        if value is not None:
            allowed.add(str(value))
    present_ids = {flag.id for flag in flags if flag.state == FlagState.PRESENT}
    for rule in rules.flags:
        if rule.id in present_ids:
            for name in _criterion_params(rule.present_when):
                allowed.add(str(rules.params[name].value))
    not_assessable = sum(1 for flag in flags if flag.state == FlagState.NOT_ASSESSABLE)
    allowed.update(
        {
            str(len(present_ids)),
            str(not_assessable),
            str(missing_count),
            str(len(flags)),
            str(len(rules.red_flags)),
        }
    )
    return frozenset(allowed)


def validate_explanation(output: dict[str, Any], context: ValidationContext) -> ValidatorResult:
    """Validate an explanation document against ground truth.

    Args:
        output: Raw LLM output mapping.
        context: Ground truth context.

    Returns:
        Validation outcome with reasons.
    """
    try:
        parsed = ExplainerOutput.model_validate(output)
    except ValidationError as exc:
        return ValidatorResult(ok=False, errors=(f"schema: {exc.errors()[0]['msg']}",))
    errors: list[str] = []
    if parsed.language != context.language:
        errors.append("language mismatch")
    explained = {entry.flag_id for entry in parsed.flags}
    for flag_id in sorted(explained - set(context.all_flag_ids)):
        errors.append(f"unknown flag {flag_id}")
    for flag_id in sorted(set(context.present_flag_ids) - explained):
        errors.append(f"present flag {flag_id} omitted")
    for entry in parsed.flags:
        if entry.flag_id in context.not_assessable_ids and not entry.unknowns:
            errors.append(f"missing unknowns for {entry.flag_id}")
        for source in sorted(set(entry.sources) - set(context.provided_sources)):
            errors.append(f"unknown source {source} cited for {entry.flag_id}")
    texts = (
        [parsed.summary, parsed.next_step_text, parsed.disclaimer]
        + [entry.explanation for entry in parsed.flags]
        + [unknown for entry in parsed.flags for unknown in entry.unknowns]
        + [entry.modifiable_note for entry in parsed.flags if entry.modifiable_note]
    )
    _check_banned(texts, context.language, brief=False, errors=errors)
    for hit in find_other_route(parsed.next_step_text, context.route.value):
        errors.append(f"implies a different route: {hit}")
    _check_numbers(texts, context.allowed_numbers, errors=errors)
    _check_disclaimer(parsed.disclaimer, context.language, errors=errors)
    return ValidatorResult(ok=not errors, errors=tuple(errors))


def validate_brief(output: dict[str, Any], context: ValidationContext) -> ValidatorResult:
    """Validate a clinician brief document against ground truth.

    Args:
        output: Raw LLM output mapping.
        context: Ground truth context.

    Returns:
        Validation outcome with reasons.
    """
    try:
        parsed = BriefOutput.model_validate(output)
    except ValidationError as exc:
        return ValidatorResult(ok=False, errors=(f"schema: {exc.errors()[0]['msg']}",))
    errors: list[str] = []
    if parsed.language != context.language:
        errors.append("language mismatch")
    if parsed.route != context.route:
        errors.append("route mismatch")
    explained = {entry.flag_id for entry in parsed.flags}
    for flag_id in sorted(explained - set(context.all_flag_ids)):
        errors.append(f"unknown flag {flag_id}")
    for flag_id in sorted(set(context.present_flag_ids) - explained):
        errors.append(f"present flag {flag_id} omitted")
    for entry in parsed.flags:
        for source in sorted(set(entry.sources) - set(context.provided_sources)):
            errors.append(f"unknown source {source} cited for {entry.flag_id}")
    texts = (
        [parsed.reason_for_contact, parsed.route_rationale, parsed.scope_note]
        + [entry.label for entry in parsed.flags]
        + [entry.note for entry in parsed.flags if entry.note]
        + list(parsed.missing_information)
    )
    _check_banned(texts, context.language, brief=True, errors=errors)
    _check_numbers(texts, context.allowed_numbers, errors=errors)
    return ValidatorResult(ok=not errors, errors=tuple(errors))
