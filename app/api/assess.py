"""Assessment endpoints."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import ConsentedIntakeUser, CurrentUserDep, LanguageDep, SessionDep, SettingsDep
from app.orchestrator.pipeline import run_assessment
from app.rules_engine.loader import load_rules
from app.schemas.assess import AssessResponse
from app.services.assessment import (
    build_assess_response,
    get_accessible_assessment,
    get_trace,
    latest_explanation,
)
from app.services.content import load_snippets, load_static_safety
from app.services.intake import load_intake_schema

router = APIRouter(tags=["assessments"])


@router.post("/assess", response_model=AssessResponse, status_code=201)
def post_assess(
    user: ConsentedIntakeUser,
    session: SessionDep,
    settings: SettingsDep,
    language: LanguageDep,
) -> AssessResponse:
    """Run the assessment pipeline for the caller.

    Args:
        user: Authenticated user with intake consent.
        session: Request database session.
        settings: Application settings.
        language: Response language.

    Returns:
        Full assessment response.
    """
    result = run_assessment(session, user, settings, language)
    schema = load_intake_schema(settings.content_dir)
    rules = load_rules(Path(settings.rules_dir), settings.rules_version)
    safety = load_static_safety(settings.content_dir, language)
    snippets = load_snippets(settings.content_dir, language)
    return build_assess_response(
        result.assessment, result.explanation, result.trace.id, schema, rules, safety, snippets
    )


@router.get("/assessments/{assessment_id}", response_model=AssessResponse)
def get_assessment(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep, assessment_id: UUID
) -> AssessResponse:
    """Return one stored assessment with its latest explanation.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.
        assessment_id: Assessment id.

    Returns:
        Full assessment response.
    """
    row = get_accessible_assessment(session, user, assessment_id)
    explanation = latest_explanation(session, row.id)
    schema = load_intake_schema(settings.content_dir)
    rules = load_rules(Path(settings.rules_dir), settings.rules_version)
    safety = load_static_safety(settings.content_dir, explanation.language)
    snippets = load_snippets(settings.content_dir, explanation.language)
    trace = get_trace(session, row.id)
    return build_assess_response(row, explanation, trace.id, schema, rules, safety, snippets)
