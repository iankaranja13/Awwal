"""Health-check endpoints."""

from fastapi import APIRouter

from app import __version__
from app.core.deps import SettingsDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


def build_health_response(environment: str) -> HealthResponse:
    """Build the liveness payload.

    Args:
        environment: Deployment environment name.

    Returns:
        The health response payload.
    """
    return HealthResponse(status="ok", version=__version__, environment=environment)


@router.get("/health", response_model=HealthResponse, summary="Liveness probe.")
def get_health(settings: SettingsDep) -> HealthResponse:
    """Return service liveness and version.

    Args:
        settings: Injected application settings.

    Returns:
        The health response payload.
    """
    return build_health_response(settings.app_env)
