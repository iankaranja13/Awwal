"""Assessment pipeline: consent, intake, rules, explanation, persistence."""

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import ConsentScope, ExplanationSource, FlagState, Language, Route
from app.core.errors import ConsentRequiredError
from app.llm.templates import build_template_explanation
from app.models import Assessment, Explanation, User, WorkflowTrace
from app.orchestrator.trace import TraceRecorder
from app.rules_engine.evaluator import compute_derived
from app.rules_engine.loader import load_rules
from app.rules_engine.models import AssessmentInput, FlagResult
from app.rules_engine.triage import evaluate_flag_stage, evaluate_red_stage, select_route
from app.schemas.explain import ExplainerOutput
from app.services.consent import has_consent
from app.services.content import (
    ContentError,
    load_explainer,
    load_next_steps,
    load_snippets,
    load_static_safety,
)
from app.services.intake import get_stored_answers, load_intake_schema


@dataclass(frozen=True)
class PipelineResult:
    """Rows created by one pipeline run."""

    assessment: Assessment
    explanation: Explanation
    trace: WorkflowTrace


def run_assessment(
    session: Session, user: User, settings: Settings, language: Language
) -> PipelineResult:
    """Run the full assessment pipeline with tracing.

    Args:
        session: Database session.
        user: Assessed user.
        settings: Application settings.
        language: Explanation language.

    Returns:
        Created assessment, explanation and trace rows.

    Raises:
        ConsentRequiredError: If intake consent is missing.
        ContentError: If required content is missing.
        CryptoError: If stored intake cannot be decrypted.
    """
    rules = load_rules(Path(settings.rules_dir), settings.rules_version)
    recorder = TraceRecorder(rules_version=rules.version)
    with recorder.timed("consent_check") as detail:
        detail["scope"] = ConsentScope.INTAKE.value
        if not has_consent(session, user.id, ConsentScope.INTAKE):
            raise ConsentRequiredError(details={"scope": ConsentScope.INTAKE.value})
    with recorder.timed("load_intake") as detail:
        schema = load_intake_schema(settings.content_dir)
        stored, _ = get_stored_answers(session, user, settings.field_encryption_key)
        inputs = AssessmentInput.model_validate({"answers": stored})
        detail["answered_count"] = len(stored)
        detail["schema_version"] = schema.schema_version
    with recorder.timed("red_flag_evaluation") as detail:
        derived = compute_derived(inputs.answers)
        red_results = evaluate_red_stage(rules, inputs, derived)
        present_red = [result.id for result in red_results if result.present]
        detail["present"] = present_red
    if present_red:
        recorder.skipped("flag_evaluation", {"reason": "red_flag_short_circuit"})
        flag_results = []
    else:
        with recorder.timed("flag_evaluation") as detail:
            flag_results = evaluate_flag_stage(rules, inputs, derived)
            detail["present"] = sum(
                1 for flag in flag_results if flag.state == FlagState.PRESENT
            )
            detail["not_assessable"] = sum(
                1 for flag in flag_results if flag.state == FlagState.NOT_ASSESSABLE
            )
    with recorder.timed("triage") as detail:
        decision = select_route(rules, flag_results, red_results)
        detail["route"] = decision.route.value
    with recorder.timed("explanation") as detail:
        output, source = _explain(
            settings,
            language,
            decision.route,
            flag_results,
            decision.missing_items,
            decision.static_message_id,
            decision.urgent,
        )
        detail["source"] = source.value
    with recorder.timed("persist") as detail:
        assessment = Assessment(
            user_id=user.id,
            rules_version=rules.version,
            flags=[flag.model_dump(mode="json") for flag in flag_results],
            missing_items=decision.missing_items,
            route=decision.route,
            route_reason=decision.route_reason,
            urgent=decision.urgent,
        )
        session.add(assessment)
        session.flush()
        explanation = Explanation(
            assessment_id=assessment.id,
            language=language,
            source=source,
            model=None,
            prompt_version=None,
            text=output.model_dump(mode="json"),
            validator_result=None,
        )
        session.add(explanation)
        session.flush()
        detail["assessment_id"] = str(assessment.id)
    trace = WorkflowTrace(
        assessment_id=assessment.id,
        steps=[dataclasses.asdict(step) for step in recorder.steps],
        duration_ms=recorder.duration_ms(),
    )
    session.add(trace)
    session.flush()
    return PipelineResult(assessment=assessment, explanation=explanation, trace=trace)


def _explain(
    settings: Settings,
    language: Language,
    route: Route,
    flag_results: list[FlagResult],
    missing_items: list[str],
    static_message_id: str | None,
    urgent: bool,
) -> tuple[ExplainerOutput, ExplanationSource]:
    """Build the static or template explanation for one decision.

    Args:
        settings: Application settings.
        language: Explanation language.
        route: Selected route.
        flag_results: Evaluated flags.
        missing_items: Missing key item ids.
        static_message_id: Urgent static message id, if any.
        urgent: Whether a red flag short-circuited the pipeline.

    Returns:
        Explanation document with its source.

    Raises:
        ContentError: If required content is missing.
    """
    explainer = load_explainer(settings.content_dir, language)
    next_steps = load_next_steps(settings.content_dir, language)
    if urgent:
        if static_message_id is None:
            raise ContentError("Urgent decision without a static message.")
        safety = load_static_safety(settings.content_dir, language)
        message = safety.messages[static_message_id]
        output = ExplainerOutput(
            language=language,
            summary=message.title,
            flags=[],
            next_step_text=next_steps.steps[Route.URGENT.value],
            disclaimer=explainer.disclaimer,
        )
        return output, ExplanationSource.STATIC
    schema = load_intake_schema(settings.content_dir)
    why_map = {
        item.id: item.why_we_ask.en if language == Language.EN else item.why_we_ask.ar
        for item in schema.items
    }
    missing_why = {item_id: why_map[item_id] for item_id in missing_items}
    snippets = load_snippets(settings.content_dir, language)
    output = build_template_explanation(
        route, flag_results, missing_why, language, snippets, next_steps, explainer
    )
    return output, ExplanationSource.TEMPLATE
