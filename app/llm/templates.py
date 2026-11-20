"""Deterministic template explanations (no model calls)."""

from collections.abc import Mapping

from app.core.enums import FlagState, Language, Route
from app.rules_engine.models import FlagResult
from app.schemas.explain import BriefFlag, BriefOutput, ExplainedFlag, ExplainerOutput
from app.services.content import ContentError, ExplainerFile, NextStepsFile, SnippetsFile


def _required(mapping: dict[str, str], key: str, kind: str) -> str:
    """Fetch required content or fail with a clear error.

    Args:
        mapping: Content entries by key.
        key: Entry key.
        kind: Entry kind for error messages.

    Returns:
        The content entry.

    Raises:
        ContentError: If the entry is missing.
    """
    try:
        return mapping[key]
    except KeyError as exc:
        raise ContentError(f"Missing {kind} {key}.") from exc


def build_template_explanation(
    route: Route,
    flags: list[FlagResult],
    why_map: dict[str, str],
    language: Language,
    snippets: SnippetsFile,
    next_steps: NextStepsFile,
    explainer: ExplainerFile,
    excerpt_index: Mapping[str, tuple[str, ...]] | None = None,
) -> ExplainerOutput:
    """Build a deterministic explanation from snippets and templates.

    Args:
        route: Selected route.
        flags: Evaluated flag outcomes.
        why_map: Why-we-ask text by item id.
        language: Explanation language.
        snippets: Flag snippets for the language.
        next_steps: Next-step texts for the language.
        explainer: Template strings for the language.
        excerpt_index: Excerpt ids by flag id (empty cites when omitted).

    Returns:
        Explanation document in the shared output contract.
    """
    present = [flag for flag in flags if flag.state == FlagState.PRESENT]
    if present:
        summary = explainer.summary_signals.format(count=len(present))
    elif route == Route.SELF_CARE_PROVISIONAL:
        summary = explainer.summary_provisional
    else:
        summary = explainer.summary_clear
    index = excerpt_index or {}
    explained = [
        ExplainedFlag(
            flag_id=flag.id,
            explanation=_required(snippets.snippets, flag.snippet_id, "snippet"),
            unknowns=[why_map[field] for field in flag.missing_fields if field in why_map],
            modifiable_note=explainer.modifiable_note if flag.modifiable else None,
            sources=list(index.get(flag.id, ())),
        )
        for flag in flags
    ]
    return ExplainerOutput(
        language=language,
        summary=summary,
        flags=explained,
        next_step_text=_required(next_steps.steps, route.value, "next step"),
        disclaimer=explainer.disclaimer,
    )


def build_brief_template(
    route: Route,
    route_reason: list[str],
    flags: list[FlagResult],
    missing_items: list[str],
    language: Language,
    explainer: ExplainerFile,
    scope_note: str,
    excerpt_index: Mapping[str, tuple[str, ...]] | None = None,
) -> BriefOutput:
    """Build a deterministic clinician brief from structured data.

    Args:
        route: Selected route.
        route_reason: Driver rule ids.
        flags: Evaluated flag outcomes.
        missing_items: Missing key item ids.
        language: Brief language.
        explainer: Template strings for the language.
        scope_note: Record scope note.
        excerpt_index: Excerpt ids by flag id (empty cites when omitted).

    Returns:
        Brief document in the shared output contract.
    """
    if route_reason:
        rationale = f"{explainer.brief_rationale_prefix}: {', '.join(route_reason)}."
    else:
        rationale = explainer.brief_rationale_none
    present_labels = [
        flag.label.en if language == Language.EN else flag.label.ar
        for flag in flags
        if flag.state == FlagState.PRESENT
    ]
    if present_labels:
        reason = f"{', '.join(present_labels)}."
    elif route_reason:
        reason = f"{', '.join(route_reason)}."
    else:
        reason = explainer.brief_rationale_none
    index = excerpt_index or {}
    entries = [
        BriefFlag(
            flag_id=flag.id,
            state=flag.state,
            label=flag.label.en if language == Language.EN else flag.label.ar,
            source=flag.source,
            note=None,
            sources=list(index.get(flag.id, ())),
        )
        for flag in flags
    ]
    return BriefOutput(
        language=language,
        reason_for_contact=reason,
        flags=entries,
        missing_information=list(missing_items),
        route=route,
        route_rationale=rationale,
        scope_note=scope_note,
    )
