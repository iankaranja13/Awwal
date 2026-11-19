"""Role account login endpoint."""

from datetime import timedelta

from fastapi import APIRouter, Request

from app.core.clock import utc_now
from app.core.deps import SessionDep, SettingsDep
from app.core.rate_limit import bucket_key, check_rate_limit
from app.core.security import create_access_token
from app.schemas.referral import LoginRequest
from app.schemas.session import SessionResponse
from app.services.users import authenticate

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=SessionResponse)
def post_login(
    request: Request, session: SessionDep, settings: SettingsDep, body: LoginRequest
) -> SessionResponse:
    """Log in a seeded role account and return its token.

    Args:
        request: Incoming request (for rate limiting).
        session: Request database session.
        settings: Application settings.
        body: Handle with password.

    Returns:
        Session with access token.
    """
    check_rate_limit(
        request.app.state.rate_limit_buckets,
        bucket_key(request),
        settings.rate_limit_per_minute,
        settings.rate_limit_window_seconds,
        utc_now(),
    )
    user = authenticate(session, body.handle, body.password)
    token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        secret=settings.jwt_secret,
        expires_in=timedelta(minutes=settings.jwt_expire_minutes),
    )
    return SessionResponse(
        user_id=user.id, handle=user.pseudonymous_handle, role=user.role, token=token
    )
