"""Clinician brief generation with validation and template fallback."""

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
from app.llm.templates import build_brief_template
from app.llm.validator import (
    ValidationContext,
    ValidatorResult,
    build_allowed_numbers,
    validate_brief,
)
from app.models import User
from app.rules_engine.loader import load_rules
from app.rules_engine.models import AssessmentInput, FlagResult
from app.schemas.explain import BriefOutput
from app.services.assessment import get_accessible_assessment, latest_explanation
from app.services.audit import record as record_audit
from app.services.content import load_explainer
from app.services.intake import get_stored_answers

logger = logging.getLogger("awwal.brief")


@dataclass(frozen=True)
class BriefResult:
    """Generated brief with fallback metadata (briefs are never stored)."""

    brief: BriefOutput
    source: ExplanationSource
    used_fallback: bool
    model: str
    validator: ValidatorResult | None


def _brief_user_json(
    route: str,
    route_reason: list[str],
    flags: list[FlagResult],
    missing_items: list[str],
    language: Language,
    scope_note: str,
    reason_hint: str,
    rationale_hint: str,
) -> dict[str, Any]:
    """Build structured LLM input without personal data.

    Args:
        route: Selected route value.
        route_reason: Driver rule ids.
        flags: Evaluated flag outcomes.
        missing_items: Missing key item ids.
        language: Requested language.
        scope_note: Record scope note.
        reason_hint: Template reason for contact.
        rationale_hint: Template route rationale.

    Returns:
        Job input mapping.
    """
    return {
        "job": "brief",
        "language": language.value,
        "route": route,
        "route_reason": list(route_reason),
        "flags": [
            {
                "flag_id": flag.id,
                "state": flag.state.value,
                "label": flag.label.en if language == Language.EN else flag.label.ar,
                "source": flag.source,
            }
            for flag in flags
        ],
        "missing_information": list(missing_items),
        "scope_note": scope_note,
        "reason_hint": reason_hint,
        "rationale_hint": rationale_hint,
    }


def build_brief(
    session: Session,
    user: User,
    assessment_id: UUID,
    language: Language | None,
    settings: Settings,
    client: LLMClient | None = None,
) -> BriefResult:
    """Generate a clinician brief with validation and fallback.

    Owners always qualify; clinicians qualify with an active share covering
    the assessment. Briefs are generated on demand and audited, but never
    stored.

    Args:
        session: Database session.
        user: Requesting user.
        assessment_id: Assessment id.
        language: Requested language (defaults to the stored one).
        settings: Application settings.
        client: Optional injected client (tests use stubs).

    Returns:
        Generated brief with fallback metadata.
    """
    row = get_accessible_assessment(session, user, assessment_id, "brief.read")
    latest = latest_explanation(session, row.id)
    target = language if language is not None else latest.language
    rules = load_rules(Path(settings.rules_dir), settings.rules_version)
    flags = [FlagResult.model_validate(raw) for raw in row.flags]
    explainer = load_explainer(settings.content_dir, target)
    if row.user_id == user.id:
        scope_note = explainer.brief_scope_owner
    else:
        scope_note = explainer.brief_scope_shared
    template = build_brief_template(
        row.route,
        list(row.route_reason),
        flags,
        list(row.missing_items),
        target,
        explainer,
        scope_note,
    )
    stored, _ = get_stored_answers(session, user, settings.field_encryption_key)
    inputs = AssessmentInput.model_validate({"answers": stored})
    context = ValidationContext(
        language=target,
        route=row.route,
        present_flag_ids=frozenset(flag.id for flag in flags if flag.state == FlagState.PRESENT),
        all_flag_ids=frozenset(flag.id for flag in flags),
        not_assessable_ids=frozenset(),
        allowed_numbers=build_allowed_numbers(rules, flags, len(row.missing_items), inputs),
    )
    user_json = _brief_user_json(
        row.route.value,
        list(row.route_reason),
        flags,
        list(row.missing_items),
        target,
        template.scope_note,
        template.reason_for_contact,
        template.route_rationale,
    )
    model = "mock" if settings.llm_provider == "mock" else settings.llm_model
    prompt_version = None if settings.llm_provider == "mock" else PROMPT_VERSION
    try:
        llm = client if client is not None else create_client(settings)
        raw = llm.generate(
            load_prompt("brief"),
            user_json,
            BriefOutput.model_json_schema(),
            settings.llm_timeout_seconds,
        )
        validation = validate_brief(raw, context)
        if validation.ok:
            parsed = BriefOutput.model_validate(raw)
            _audit(session, user, row.id, model, False, prompt_version)
            return BriefResult(
                brief=parsed,
                source=ExplanationSource.LLM,
                used_fallback=False,
                model=model,
                validator=validation,
            )
        logger.warning("llm brief rejected: %s", "; ".join(validation.errors))
        _audit(session, user, row.id, model, True, prompt_version)
        return BriefResult(
            brief=template,
            source=ExplanationSource.TEMPLATE,
            used_fallback=True,
            model=model,
            validator=validation,
        )
    except LLMError as exc:
        logger.warning("llm brief failed: %s", exc)
        validation = ValidatorResult(ok=False, errors=(f"provider: {exc}",))
        _audit(session, user, row.id, model, True, prompt_version)
        return BriefResult(
            brief=template,
            source=ExplanationSource.TEMPLATE,
            used_fallback=True,
            model=model,
            validator=validation,
        )


def _audit(
    session: Session,
    user: User,
    assessment_id: UUID,
    model: str,
    used_fallback: bool,
    prompt_version: str | None,
) -> None:
    """Audit one brief generation.

    Args:
        session: Database session.
        user: Requesting user.
        assessment_id: Assessment id.
        model: Model name attempted.
        used_fallback: Whether templates were used.
        prompt_version: Prompt version, if any.
    """
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="brief.generated",
        object_type="assessment",
        object_id=assessment_id,
        detail={"model": model, "used_fallback": used_fallback, "prompt": prompt_version},
    )
