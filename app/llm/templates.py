"""Deterministic template explanations (no model calls)."""

from app.core.enums import FlagState, Language, Route
from app.rules_engine.models import FlagResult
from app.schemas.explain import ExplainedFlag, ExplainerOutput
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
    missing_why: dict[str, str],
    language: Language,
    snippets: SnippetsFile,
    next_steps: NextStepsFile,
    explainer: ExplainerFile,
) -> ExplainerOutput:
    """Build a deterministic explanation from snippets and templates.

    Args:
        route: Selected route.
        flags: Evaluated flag outcomes.
        missing_why: Why-we-ask text by missing item id.
        language: Explanation language.
        snippets: Flag snippets for the language.
        next_steps: Next-step texts for the language.
        explainer: Template strings for the language.

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
    explained = [
        ExplainedFlag(
            flag_id=flag.id,
            explanation=_required(snippets.snippets, flag.snippet_id, "snippet"),
            unknowns=[missing_why[field] for field in flag.missing_fields if field in missing_why],
            modifiable_note=explainer.modifiable_note if flag.modifiable else None,
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
