"""Assessment response building and owned-record access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Language, Role, Route
from app.core.errors import ForbiddenError, NotFoundError
from app.models import Assessment, Explanation, User, WorkflowTrace
from app.rules_engine.models import FlagResult, RuleSet
from app.schemas.assess import (
    AssessFlag,
    AssessResponse,
    MissingItem,
    NextStep,
    StaticSafetyMessage,
    TraceResponse,
    TraceStep,
)
from app.schemas.explain import ExplainedFlag, ExplainerOutput
from app.schemas.intake import IntakeSchemaDocument
from app.services.audit import record as record_audit
from app.services.content import ContentError, SnippetsFile, StaticSafetyFile
from app.services.share import has_active_share

ROUTE_ACTIONS: dict[Route, list[str]] = {
    Route.URGENT: ["seek_urgent_care"],
    Route.ANDROLOGY_UROLOGY: ["book_specialist"],
    Route.FERTILITY_SERVICES: ["book_fertility"],
    Route.PRIMARY_CARE: ["book_primary_care"],
    Route.SELF_CARE_PROVISIONAL: ["complete_intake"],
    Route.SELF_CARE: ["review_self_care"],
}


def get_own_assessment(session: Session, user: User, assessment_id: UUID) -> Assessment:
    """Load one assessment belonging to the caller.

    Args:
        session: Database session.
        user: Authenticated user.
        assessment_id: Assessment id.

    Returns:
        The assessment row.

    Raises:
        NotFoundError: If the assessment is missing or belongs to someone else.
    """
    row = session.get(Assessment, assessment_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Assessment not found.")
    return row


def get_accessible_assessment(
    session: Session, user: User, assessment_id: UUID, read_action: str = "assessment.read"
) -> Assessment:
    """Load one assessment the caller may read, auditing clinician reads.

    Args:
        session: Database session.
        user: Authenticated user.
        assessment_id: Assessment id.
        read_action: Audit action for clinician reads.

    Returns:
        The assessment row.

    Raises:
        NotFoundError: If the assessment is missing or hidden from the caller.
        ForbiddenError: If a clinician lacks an active share.
    """
    row = session.get(Assessment, assessment_id)
    if row is None:
        raise NotFoundError("Assessment not found.")
    if row.user_id == user.id:
        return row
    if user.role != Role.CLINICIAN:
        raise NotFoundError("Assessment not found.")
    if not has_active_share(session, row.user_id, user.id, row.id):
        raise ForbiddenError("No active share covers this record.")
    record_audit(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action=read_action,
        object_type="assessment",
        object_id=row.id,
    )
    return row


def latest_explanation(session: Session, assessment_id: UUID) -> Explanation:
    """Load the latest explanation for one assessment.

    Args:
        session: Database session.
        assessment_id: Assessment id.

    Returns:
        Latest explanation row.

    Raises:
        NotFoundError: If no explanation exists.
    """
    row = session.scalars(
        select(Explanation)
        .where(Explanation.assessment_id == assessment_id)
        .order_by(Explanation.created_at.desc(), Explanation.id.desc())
    ).first()
    if row is None:
        raise NotFoundError("Assessment explanation not found.")
    return row


def get_trace(session: Session, assessment_id: UUID) -> WorkflowTrace:
    """Load the workflow trace for one assessment.

    Args:
        session: Database session.
        assessment_id: Assessment id.

    Returns:
        Trace row.

    Raises:
        NotFoundError: If no trace exists.
    """
    row = session.scalars(
        select(WorkflowTrace).where(WorkflowTrace.assessment_id == assessment_id)
    ).one_or_none()
    if row is None:
        raise NotFoundError("Workflow trace not found.")
    return row


def build_assess_response(
    assessment: Assessment,
    explanation: Explanation,
    trace_id: UUID,
    schema: IntakeSchemaDocument,
    rules: RuleSet,
    safety: StaticSafetyFile,
    snippets: SnippetsFile,
) -> AssessResponse:
    """Build the API response from stored assessment rows.

    Args:
        assessment: Stored assessment row.
        explanation: Stored explanation row to display.
        trace_id: Workflow trace id.
        schema: Intake schema document.
        rules: Loaded rule set.
        safety: Static safety messages for the explanation language.
        snippets: Flag snippets for the explanation language.

    Returns:
        Full assessment response.

    Raises:
        ContentError: If an urgent assessment lacks its red driver.
    """
    output = ExplainerOutput.model_validate(explanation.text)
    language = explanation.language
    by_flag = {entry.flag_id: entry for entry in output.flags}
    why_map = {
        item.id: item.why_we_ask.en if language == Language.EN else item.why_we_ask.ar
        for item in schema.items
    }
    flags = [
        _build_flag(FlagResult.model_validate(raw), by_flag, why_map, language, snippets)
        for raw in assessment.flags
    ]
    missing = [
        MissingItem(item_id=item_id, why_we_ask=why_map[item_id])
        for item_id in assessment.missing_items
    ]
    review = {route.id: route.requires_clinician_review for route in rules.routes}
    next_step = NextStep(
        text=output.next_step_text,
        requires_clinician_review=review[assessment.route],
        actions=ROUTE_ACTIONS[assessment.route],
    )
    static_message = _static_message(assessment, rules, safety)
    return AssessResponse(
        assessment_id=assessment.id,
        rules_version=assessment.rules_version,
        language=language,
        urgent=assessment.urgent,
        route=assessment.route,
        route_reason=list(assessment.route_reason),
        flags=flags,
        missing_items=missing,
        next_step=next_step,
        static_safety_message=static_message,
        disclaimer=output.disclaimer,
        explanation_source=explanation.source,
        trace_id=trace_id,
    )


def _build_flag(
    flag: FlagResult,
    explained: dict[str, ExplainedFlag],
    why_map: dict[str, str],
    language: Language,
    snippets: SnippetsFile,
) -> AssessFlag:
    """Build one served flag from stored data.

    Args:
        flag: Stored flag outcome.
        explained: Explanations by flag id.
        why_map: Why text by item id.
        language: Response language.
        snippets: Snippet fallback for uncovered flags.

    Returns:
        Served flag entry.
    """
    entry = explained.get(flag.id)
    if entry is None:
        text = snippets.snippets[flag.snippet_id]
    else:
        text = entry.explanation
    label = flag.label.en if language == Language.EN else flag.label.ar
    why = "; ".join(why_map[field] for field in flag.missing_fields) or None
    return AssessFlag(
        id=flag.id,
        state=flag.state,
        domain=flag.domain,
        label=label,
        reason_fields=list(flag.reason_fields),
        missing_fields=list(flag.missing_fields),
        modifiable=flag.modifiable,
        source=flag.source,
        requires_clinical_validation=flag.requires_clinical_validation,
        explanation=text,
        why_we_ask=why,
    )


def _static_message(
    assessment: Assessment, rules: RuleSet, safety: StaticSafetyFile
) -> StaticSafetyMessage | None:
    """Resolve the static safety message for urgent assessments.

    Args:
        assessment: Stored assessment row.
        rules: Loaded rule set.
        safety: Static safety messages for the response language.

    Returns:
        Static message, or None when not urgent.

    Raises:
        ContentError: If an urgent assessment lacks its red driver.
    """
    if not assessment.urgent:
        return None
    if not assessment.route_reason:
        raise ContentError("Urgent assessment without a red driver.")
    red_id = assessment.route_reason[0]
    static_id = next(rule.static_message_id for rule in rules.red_flags if rule.id == red_id)
    message = safety.messages[static_id]
    return StaticSafetyMessage(id=static_id, title=message.title, body=message.body)


def build_trace_response(trace: WorkflowTrace) -> TraceResponse:
    """Build the API response from a stored trace row.

    Args:
        trace: Stored trace row.

    Returns:
        Trace response.
    """
    steps = [TraceStep.model_validate(step) for step in trace.steps]
    return TraceResponse(
        trace_id=trace.id,
        assessment_id=trace.assessment_id,
        steps=steps,
        duration_ms=trace.duration_ms,
    )
