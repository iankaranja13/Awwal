"""Explanation regeneration with LLM validation and template fallback."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import ExplanationSource, FlagState, Language
from app.llm.client import PROMPT_VERSION, LLMClient, create_client, load_prompt
from app.llm.errors import LLMError
from app.llm.templates import build_template_explanation
from app.llm.validator import (
    ValidationContext,
    ValidatorResult,
    build_allowed_numbers,
    validate_explanation,
)
from app.models import Assessment, Explanation, User
from app.rules_engine.loader import load_rules
from app.rules_engine.models import AssessmentInput, FlagResult
from app.schemas.explain import ExplainerOutput
from app.services.assessment import get_own_assessment, latest_explanation
from app.services.audit import record as record_audit
from app.services.content import load_explainer, load_next_steps, load_snippets, load_static_safety
from app.services.intake import get_stored_answers, load_intake_schema

logger = logging.getLogger("awwal.explain")


@dataclass(frozen=True)
class ExplainResult:
    """Regenerated explanation with fallback metadata."""

    explanation: Explanation
    used_fallback: bool
    validator: ValidatorResult | None


def _explain_user_json(
    assessment: Assessment,
    flags: list[FlagResult],
    language: Language,
    next_step_text: str,
    disclaimer: str,
    why_map: dict[str, str],
) -> dict[str, Any]:
    """Build structured LLM input without personal data.

    Only flag ids, states, reason fields, snippet texts and the language are
    included; names, handles and contact details never reach the model.

    Args:
        assessment: Stored assessment row.
        flags: Evaluated flag outcomes.
        language: Requested language.
        next_step_text: Next step the output must stay consistent with.
        disclaimer: Required disclaimer text.
        why_map: Why text by item id.

    Returns:
        Job input mapping.
    """
    return {
        "job": "explain",
        "language": language.value,
        "route": assessment.route.value,
        "route_reason": list(assessment.route_reason),
        "flags": [
            {
                "flag_id": flag.id,
                "state": flag.state.value,
                "label": flag.label.en if language == Language.EN else flag.label.ar,
                "snippet_id": flag.snippet_id,
                "modifiable": flag.modifiable,
                "unknowns": [
                    why_map[field] for field in flag.missing_fields if field in why_map
                ],
                "reason_fields": list(flag.reason_fields),
            }
            for flag in flags
        ],
        "missing_items": list(assessment.missing_items),
        "next_step_text": next_step_text,
        "disclaimer": disclaimer,
    }


def explain_assessment(
    session: Session,
    user: User,
    assessment_id: UUID,
    language: Language | None,
    settings: Settings,
    client: LLMClient | None = None,
) -> ExplainResult:
    """Regenerate an explanation with validation and fallback.

    Urgent assessments reuse static content and never touch the LLM. Any
    provider failure or validation rejection falls back to templates.

    Args:
        session: Database session.
        user: Requesting user (must own the assessment).
        assessment_id: Assessment id.
        language: Requested language (defaults to the stored one).
        settings: Application settings.
        client: Optional injected client (tests use stubs).

    Returns:
        Stored explanation with fallback metadata.
    """
    row = get_own_assessment(session, user, assessment_id)
    latest = latest_explanation(session, row.id)
    target = language if language is not None else latest.language
    rules = load_rules(Path(settings.rules_dir), settings.rules_version)
    schema = load_intake_schema(settings.content_dir)
    flags = [FlagResult.model_validate(raw) for raw in row.flags]
    explainer = load_explainer(settings.content_dir, target)
    next_steps = load_next_steps(settings.content_dir, target)
    if row.urgent:
        red_id = row.route_reason[0]
        static_id = next(rule.static_message_id for rule in rules.red_flags if rule.id == red_id)
        safety = load_static_safety(settings.content_dir, target)
        message = safety.messages[static_id]
        output = ExplainerOutput(
            language=target,
            summary=message.title,
            flags=[],
            next_step_text=next_steps.steps["URGENT"],
            disclaimer=explainer.disclaimer,
        )
        stored = _persist(
            session, row.id, target, ExplanationSource.STATIC, None, None, output, None
        )
        return ExplainResult(explanation=stored, used_fallback=False, validator=None)
    why_map = {
        item.id: item.why_we_ask.en if target == Language.EN else item.why_we_ask.ar
        for item in schema.items
    }
    snippets = load_snippets(settings.content_dir, target)
    template = build_template_explanation(
        row.route, flags, why_map, target, snippets, next_steps, explainer
    )
    stored_answers, _ = get_stored_answers(session, user, settings.field_encryption_key)
    inputs = AssessmentInput.model_validate({"answers": stored_answers})
    context = ValidationContext(
        language=target,
        route=row.route,
        present_flag_ids=frozenset(
            flag.id for flag in flags if flag.state == FlagState.PRESENT
        ),
        all_flag_ids=frozenset(flag.id for flag in flags),
        not_assessable_ids=frozenset(
            flag.id for flag in flags if flag.state == FlagState.NOT_ASSESSABLE
        ),
        allowed_numbers=build_allowed_numbers(rules, flags, len(row.missing_items), inputs),
    )
    user_json = _explain_user_json(
        row, flags, target, template.next_step_text, template.disclaimer, why_map
    )
    model, prompt_version = _model_info(settings)
    try:
        llm = client if client is not None else create_client(settings)
        raw = llm.generate(
            load_prompt("explain"),
            user_json,
            ExplainerOutput.model_json_schema(),
            settings.llm_timeout_seconds,
        )
        validation = validate_explanation(raw, context)
        if validation.ok:
            parsed = ExplainerOutput.model_validate(raw)
            stored = _persist(
                session,
                row.id,
                target,
                ExplanationSource.LLM,
                model,
                prompt_version,
                parsed,
                validation,
            )
            _audit(session, user, stored.id, model, False)
            return ExplainResult(explanation=stored, used_fallback=False, validator=validation)
        logger.warning("llm explanation rejected: %s", "; ".join(validation.errors))
        stored = _persist(
            session, row.id, target, ExplanationSource.TEMPLATE, None, None, template, validation
        )
        _audit(session, user, stored.id, model, True)
        return ExplainResult(explanation=stored, used_fallback=True, validator=validation)
    except LLMError as exc:
        logger.warning("llm explanation failed: %s", exc)
        validation = ValidatorResult(ok=False, errors=(f"provider: {exc}",))
        stored = _persist(
            session, row.id, target, ExplanationSource.TEMPLATE, None, None, template, validation
        )
        _audit(session, user, stored.id, model, True)
        return ExplainResult(explanation=stored, used_fallback=True, validator=validation)


def _model_info(settings: Settings) -> tuple[str, str | None]:
    """Resolve recorded model name and prompt version.

    Args:
        settings: Application settings.

    Returns:
        Model name with prompt version (None for the mock provider).
    """
    if settings.llm_provider == "mock":
        return "mock", None
    return settings.llm_model, PROMPT_VERSION


def _persist(
    session: Session,
    assessment_id: UUID,
    language: Language,
    source: ExplanationSource,
    model: str | None,
    prompt_version: str | None,
    output: ExplainerOutput,
    validation: ValidatorResult | None,
) -> Explanation:
    """Persist one explanation row.

    Args:
        session: Database session.
        assessment_id: Assessment id.
        language: Explanation language.
        source: Explanation origin.
        model: Model name, if any.
        prompt_version: Prompt version, if any.
        output: Explanation document.
        validation: Validator outcome, if any.

    Returns:
        Persisted row (flushed; committed by the caller).
    """
    row = Explanation(
        assessment_id=assessment_id,
        language=language,
        source=source,
        model=model,
        prompt_version=prompt_version,
        text=output.model_dump(mode="json"),
        validator_result=validation.to_dict() if validation is not None else None,
    )
    session.add(row)
    session.flush()
    return row


def _audit(
    session: Session, user: User, explanation_id: UUID, model: str, used_fallback: bool
) -> None:
    """Audit one explanation generation.

    Args:
        session: Database session.
        user: Requesting user.
        explanation_id: Stored explanation id.
        model: Model name attempted.
        used_fallback: Whether templates were used.
    """
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="explanation.generated",
        object_type="explanation",
        object_id=explanation_id,
        detail={"model": model, "used_fallback": used_fallback},
    )
