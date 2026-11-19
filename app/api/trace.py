"""Workflow trace endpoints."""

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import CurrentUserDep, SessionDep
from app.schemas.assess import TraceResponse
from app.services.assessment import build_trace_response, get_own_assessment, get_trace

router = APIRouter(tags=["trace"])


@router.get("/trace/{assessment_id}", response_model=TraceResponse)
def get_assessment_trace(
    user: CurrentUserDep, session: SessionDep, assessment_id: UUID
) -> TraceResponse:
    """Return the workflow trace for one assessment.

    Args:
        user: Authenticated user.
        session: Request database session.
        assessment_id: Assessment id.

    Returns:
        Trace response with ordered steps.
    """
    row = get_own_assessment(session, user, assessment_id)
    return build_trace_response(get_trace(session, row.id))
