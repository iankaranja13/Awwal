"""Explanation and brief endpoints."""

from fastapi import APIRouter

from app.core.deps import CurrentUserDep, LLMClientDep, SessionDep, SettingsDep
from app.schemas.explain import (
    BriefRequest,
    BriefResponse,
    ExplainRequest,
    ExplainResponse,
    ExplainerOutput,
    ValidatorReport,
)
from app.services.brief import build_brief
from app.services.explain import explain_assessment

router = APIRouter(tags=["explain"])


@router.post("/explain", response_model=ExplainResponse)
def post_explain(
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    llm: LLMClientDep,
    body: ExplainRequest,
) -> ExplainResponse:
    """Regenerate an explanation in a language.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.
        llm: Configured LLM client.
        body: Assessment id with optional language.

    Returns:
        Stored explanation with fallback metadata.
    """
    result = explain_assessment(session, user, body.assessment_id, body.language, settings, llm)
    output = ExplainerOutput.model_validate(result.explanation.text)
    validator = (
        ValidatorReport(ok=result.validator.ok, errors=list(result.validator.errors))
        if result.validator is not None
        else None
    )
    return ExplainResponse(
        assessment_id=body.assessment_id,
        language=result.explanation.language,
        explanation=output,
        source=result.explanation.source,
        used_fallback=result.used_fallback,
        model=result.explanation.model,
        validator=validator,
    )


@router.post("/brief", response_model=BriefResponse)
def post_brief(
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    llm: LLMClientDep,
    body: BriefRequest,
) -> BriefResponse:
    """Generate a clinician brief for the caller's own assessment.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.
        llm: Configured LLM client.
        body: Assessment id with optional language.

    Returns:
        Generated brief with fallback metadata.
    """
    result = build_brief(session, user, body.assessment_id, body.language, settings, llm)
    return BriefResponse(
        assessment_id=body.assessment_id,
        language=result.brief.language,
        brief=result.brief,
        source=result.source,
        used_fallback=result.used_fallback,
        model=result.model,
    )
