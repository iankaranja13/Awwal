"""FastAPI application factory and router wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.consent import router as consent_router
from app.api.health import build_health_response, router as health_router
from app.api.intake import router as intake_router
from app.api.sessions import router as sessions_router
from app.core.config import Settings, get_settings
from app.core.database import create_engine_for, create_session_factory
from app.core.deps import SettingsDep
from app.core.errors import register_error_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.schemas.health import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings override (tests inject isolated values).

    Returns:
        The configured FastAPI application.
    """
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved.log_level)
    engine = create_engine_for(resolved.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Dispose the database engine on shutdown.

        Args:
            _app: Application instance (unused).

        Yields:
            Control to the running application.
        """
        yield
        engine.dispose()

    app = FastAPI(
        title="Awwal API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.session_factory = create_session_factory(engine)
    app.state.rate_limit_buckets = {}
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Accept-Language", "Authorization", "Content-Type", "X-Request-ID"],
    )
    register_error_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(sessions_router, prefix="/api/v1")
    app.include_router(consent_router, prefix="/api/v1")
    app.include_router(intake_router, prefix="/api/v1")

    @app.get("/health", response_model=HealthResponse, include_in_schema=False)
    def health_alias(settings_dep: SettingsDep) -> HealthResponse:
        """Serve the liveness probe without the API prefix.

        Args:
            settings_dep: Injected application settings.

        Returns:
            The health response payload.
        """
        return build_health_response(settings_dep.app_env)

    return app


app = create_app()
