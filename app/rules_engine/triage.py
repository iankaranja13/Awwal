"""Route selection over evaluated flags and red flags."""

from dataclasses import dataclass

from app.core.enums import FlagState, Route
from app.rules_engine.evaluator import compute_derived
from app.rules_engine.flags import evaluate_flag, evaluate_red_flag
from app.rules_engine.models import (
    AssessmentInput,
    EngineResult,
    FlagResult,
    RedFlagResult,
    RuleSet,
)


@dataclass(frozen=True)
class RouteDecision:
    """Selected route with drivers and missing items."""

    route: Route
    route_reason: list[str]
    missing_items: list[str]
    urgent: bool
    static_message_id: str | None


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


def evaluate_red_stage(
    rules: RuleSet, inputs: AssessmentInput, derived: dict[str, float | None]
) -> list[RedFlagResult]:
    """Evaluate all red flags (orchestrator stage).

    Args:
        rules: Loaded rule set.
        inputs: Answers to evaluate.
        derived: Derived values by field name.

    Returns:
        Red flag outcomes in file order.
    """
    return [evaluate_red_flag(rule, inputs, derived) for rule in rules.red_flags]


def evaluate_flag_stage(
    rules: RuleSet, inputs: AssessmentInput, derived: dict[str, float | None]
) -> list[FlagResult]:
    """Evaluate all flags with three-state logic (orchestrator stage).

    Args:
        rules: Loaded rule set.
        inputs: Answers to evaluate.
        derived: Derived values by field name.

    Returns:
        Flag outcomes in file order.
    """
    return [evaluate_flag(rule, inputs, derived) for rule in rules.flags]


def select_route(
    rules: RuleSet, flag_results: list[FlagResult], red_results: list[RedFlagResult]
) -> RouteDecision:
    """Select one route from evaluated flags and red flags.

    Args:
        rules: Loaded rule set.
        flag_results: Evaluated flags (empty when short-circuited).
        red_results: Evaluated red flags.

    Returns:
        Route decision with drivers and missing items.
    """
    present_red = [result.id for result in red_results if result.present]
    if present_red:
        first = next(result for result in red_results if result.present)
        return RouteDecision(
            route=Route.URGENT,
            route_reason=present_red,
            missing_items=[],
            urgent=True,
            static_message_id=first.static_message_id,
        )
    flags_by_id = {rule.id: rule for rule in rules.flags}
    present = [result for result in flag_results if result.state == FlagState.PRESENT]
    ttc_present = any(flags_by_id[result.id].is_ttc_criterion for result in present)
    maybe_counted = [(result, _counted_route(result, ttc_present)) for result in present]
    counted = [(result, route) for result, route in maybe_counted if route is not None]
    if counted:
        precedence = {route.id: route.precedence for route in rules.routes}
        chosen = max((route for _, route in counted), key=precedence.__getitem__)
        return RouteDecision(
            route=chosen,
            route_reason=[result.id for result, route in counted if route == chosen],
            missing_items=[],
            urgent=False,
            static_message_id=None,
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
        return RouteDecision(
            route=Route.SELF_CARE_PROVISIONAL,
            route_reason=[],
            missing_items=key_missing,
            urgent=False,
            static_message_id=None,
        )
    return RouteDecision(
        route=Route.SELF_CARE,
        route_reason=[],
        missing_items=[],
        urgent=False,
        static_message_id=None,
    )


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
    red_results = evaluate_red_stage(rules, inputs, derived)
    if any(result.present for result in red_results):
        flag_results: list[FlagResult] = []
    else:
        flag_results = evaluate_flag_stage(rules, inputs, derived)
    decision = select_route(rules, flag_results, red_results)
    return EngineResult(
        rules_version=rules.version,
        route=decision.route,
        urgent=decision.urgent,
        route_reason=decision.route_reason,
        flags=flag_results,
        red_flags=red_results,
        red_flags_present=[result.id for result in red_results if result.present],
        missing_items=decision.missing_items,
        derived_values=derived_values,
        static_message_id=decision.static_message_id,
    )
