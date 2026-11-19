"""Benchmark invariant checks over assessment responses.

Each check takes plain response mappings and returns a pass flag with a
message. Variants carry clinician-free expectations only.
"""

from typing import Any

RouteMap = dict[str, int]


def check_red_flag_urgent(response: dict[str, Any]) -> tuple[bool, str]:
    """Require urgent routing when red answers were retained.

    Args:
        response: Assessment response mapping.

    Returns:
        Pass flag with a message.
    """
    if response.get("urgent") is True and response.get("route") == "URGENT":
        return True, "red retained and urgent"
    return False, f"UNDER-TRIAGE: red retained but route is {response.get('route')}"


def check_no_clear_with_missing(response: dict[str, Any]) -> tuple[bool, str]:
    """Reject plain self-care whenever key items are missing.

    Args:
        response: Assessment response mapping.

    Returns:
        Pass flag with a message.
    """
    if response.get("missing_items") and response.get("route") == "SELF_CARE":
        return False, "plain self-care despite missing items"
    return True, "no false all-clear"


def check_monotonic(
    before: dict[str, Any], after: dict[str, Any], precedence: RouteMap
) -> tuple[bool, str]:
    """Require routes not to drop when non-trigger answers go missing.

    Args:
        before: Response before missing-ing.
        after: Response after missing-ing.
        precedence: Route precedence values.

    Returns:
        Pass flag with a message.
    """
    before_rank = precedence[str(before.get("route"))]
    after_rank = precedence[str(after.get("route"))]
    if after_rank < before_rank:
        return False, f"route dropped {before.get('route')} to {after.get('route')}"
    return True, "route monotone"


def check_language_parity(first: dict[str, Any], second: dict[str, Any]) -> tuple[bool, str]:
    """Require identical routing between language runs.

    Args:
        first: First assessment response mapping.
        second: Second assessment response mapping.

    Returns:
        Pass flag with a message.
    """
    left = (
        first.get("urgent"),
        first.get("route"),
        sorted((flag["id"], flag["state"]) for flag in first.get("flags", [])),
        sorted(first.get("route_reason", [])),
    )
    right = (
        second.get("urgent"),
        second.get("route"),
        sorted((flag["id"], flag["state"]) for flag in second.get("flags", [])),
        sorted(second.get("route_reason", [])),
    )
    if left != right:
        return False, "routing differs between languages"
    return True, "routing identical between languages"
