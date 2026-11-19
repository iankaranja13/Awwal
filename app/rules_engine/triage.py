"""Route selection over evaluated flags and red flags."""

from app.core.enums import FlagState, Route
from app.rules_engine.evaluator import compute_derived
from app.rules_engine.flags import evaluate_flag, evaluate_red_flag
from app.rules_engine.models import AssessmentInput, EngineResult, FlagResult, RuleSet


def _counted_route(result: FlagResult, ttc_present: bool) -> Route | None:
    """Resolve the route one present flag actually counts toward.

    Fertility-services suggestions only count when a time-to-conceive
    criterion is present, so the route is never reached by assumption.

    Args:
        result: Present flag result.
        ttc_present: Whether any time-to-conceive criterion is present.

    Returns:
        The counted route, or None when the suggestion is guarded out.
    """
    if result.suggests_route == Route.FERTILITY_SERVICES and not ttc_present:
        return None
    return result.suggests_route


def run_triage(rules: RuleSet, inputs: AssessmentInput) -> EngineResult:
    """Evaluate answers against the rules and select one route.

    Red flags short-circuit everything; otherwise the highest-precedence
    suggested route wins, falling back to provisional and plain self-care.

    Args:
        rules: Loaded and validated rule set.
        inputs: Answers to evaluate.

    Returns:
        Engine result with flags, route and missing items.
    """
    derived = compute_derived(inputs.answers)
    derived_values = {name: value for name, value in derived.items() if value is not None}
    red_results = [evaluate_red_flag(rule, inputs, derived) for rule in rules.red_flags]
    present_red = [result for result in red_results if result.present]
    if present_red:
        present_ids = [result.id for result in present_red]
        return EngineResult(
            rules_version=rules.version,
            route=Route.URGENT,
            urgent=True,
            route_reason=present_ids,
            red_flags=red_results,
            red_flags_present=present_ids,
            derived_values=derived_values,
            static_message_id=present_red[0].static_message_id,
        )
    flags_by_id = {rule.id: rule for rule in rules.flags}
    flag_results = [evaluate_flag(rule, inputs, derived) for rule in rules.flags]
    present = [result for result in flag_results if result.state == FlagState.PRESENT]
    ttc_present = any(flags_by_id[result.id].is_ttc_criterion for result in present)
    maybe_counted = [(result, _counted_route(result, ttc_present)) for result in present]
    counted = [(result, route) for result, route in maybe_counted if route is not None]
    if counted:
        precedence = {route.id: route.precedence for route in rules.routes}
        chosen = max((route for _, route in counted), key=precedence.__getitem__)
        return EngineResult(
            rules_version=rules.version,
            route=chosen,
            urgent=False,
            route_reason=[result.id for result, route in counted if route == chosen],
            flags=flag_results,
            red_flags=red_results,
            derived_values=derived_values,
        )
    key_missing = sorted(
        {
            field
            for result in flag_results
            if result.state == FlagState.NOT_ASSESSABLE and flags_by_id[result.id].key
            for field in result.missing_fields
        }
        | {field for result in red_results for field in result.missing_fields}
    )
    if key_missing:
        return EngineResult(
            rules_version=rules.version,
            route=Route.SELF_CARE_PROVISIONAL,
            urgent=False,
            flags=flag_results,
            red_flags=red_results,
            missing_items=key_missing,
            derived_values=derived_values,
        )
    return EngineResult(
        rules_version=rules.version,
        route=Route.SELF_CARE,
        urgent=False,
        flags=flag_results,
        red_flags=red_results,
        derived_values=derived_values,
    )
