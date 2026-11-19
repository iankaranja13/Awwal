"""Session endpoints."""

from fastapi import APIRouter, Request

from app.core.clock import utc_now
from app.core.deps import SessionDep, SettingsDep
from app.core.enums import Language
from app.core.rate_limit import check_rate_limit
from app.schemas.session import SessionRequest, SessionResponse
from app.services.users import create_session

router = APIRouter(tags=["sessions"])


def _rate_limit_key(request: Request) -> str:
    """Build the rate limit bucket key for one request.

    Args:
        request: Incoming request.

    Returns:
        Bucket key combining path and client host.
    """
    host = request.client.host if request.client is not None else "unknown"
    return f"{request.url.path}:{host}"


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def post_session(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    body: SessionRequest | None = None,
) -> SessionResponse:
    """Create an anonymous session and return its token.

    Args:
        request: Incoming request (for rate limiting).
        session: Request database session.
        settings: Application settings.
        body: Optional session creation request.

    Returns:
        Created session with access token.
    """
    check_rate_limit(
        request.app.state.rate_limit_buckets,
        _rate_limit_key(request),
        settings.rate_limit_per_minute,
        settings.rate_limit_window_seconds,
        utc_now(),
    )
    language = body.language if body is not None else Language.EN
    user, token = create_session(session, settings, language)
    return SessionResponse(
        user_id=user.id, handle=user.pseudonymous_handle, role=user.role, token=token
    )
