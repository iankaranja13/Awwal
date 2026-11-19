"""Application errors mapped to stable API error codes."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("awwal.errors")

_STATUS_CODE_MAP = {
    404: ("NOT_FOUND", "Resource not found."),
    405: ("METHOD_NOT_ALLOWED", "Method not allowed."),
}


class ErrorDetail(BaseModel):
    """Machine-readable error payload."""

    code: str = Field(description="Stable error code from the API contract.")
    message: str = Field(description="Human-readable error summary.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Optional extra error context."
    )


class ErrorResponse(BaseModel):
    """Error response envelope."""

    error: ErrorDetail = Field(description="Error payload.")


class AwwalError(Exception):
    """Base class for errors that map to API error responses."""

    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."
    status_code: int = 500

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None) -> None:
        """Capture an optional message and details.

        Args:
            message: Override for the default message.
            details: Optional extra error context (never sensitive data).
        """
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        self.details: dict[str, Any] = details if details is not None else {}


class AuthError(AwwalError):
    """Authentication failed."""

    code = "UNAUTHORIZED"
    message = "Authentication failed."
    status_code = 401


class ForbiddenError(AwwalError):
    """The caller lacks permission for this action."""

    code = "FORBIDDEN"
    message = "Forbidden."
    status_code = 403


class ConsentRequiredError(AwwalError):
    """A required consent scope has not been granted."""

    code = "CONSENT_REQUIRED"
    message = "Required consent has not been granted."
    status_code = 403


class NotFoundError(AwwalError):
    """The requested resource does not exist."""

    code = "NOT_FOUND"
    message = "Resource not found."
    status_code = 404


class InvalidInputError(AwwalError):
    """The request failed domain validation."""

    code = "VALIDATION_ERROR"
    message = "Request validation failed."
    status_code = 422


class InvalidTransitionError(AwwalError):
    """The requested state transition is not allowed."""

    code = "INVALID_TRANSITION"
    message = "State transition is not allowed."
    status_code = 409


class ShareExpiredError(AwwalError):
    """The share is expired or revoked."""

    code = "SHARE_EXPIRED"
    message = "This share is expired or revoked."
    status_code = 403


class RateLimitedError(AwwalError):
    """The caller exceeded a rate limit."""

    code = "RATE_LIMITED"
    message = "Rate limit exceeded."
    status_code = 429


class CryptoError(AwwalError):
    """Stored data could not be decrypted."""

    code = "INTERNAL_ERROR"
    message = "Failed to decrypt stored data."
    status_code = 500


def register_error_handlers(app: FastAPI) -> None:
    """Register API error handlers on the application.

    Args:
        app: FastAPI application to configure.
    """

    @app.exception_handler(AwwalError)
    async def handle_awwal_error(_request: Request, exc: AwwalError) -> JSONResponse:
        """Render an application error with the stable error body.

        Args:
            _request: Incoming request (unused; required by the handler signature).
            exc: Application error carrying code, message and details.

        Returns:
            JSON response with the contract error body.
        """
        detail = ErrorDetail(code=exc.code, message=exc.message, details=exc.details)
        body = ErrorResponse(error=detail).model_dump()
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Render routing errors with the same error body shape.

        Args:
            _request: Incoming request (unused; required by the handler signature).
            exc: HTTP exception raised by routing.

        Returns:
            JSON response with the contract error body.
        """
        fallback = ("INTERNAL_ERROR", "An unexpected error occurred.")
        code, message = _STATUS_CODE_MAP.get(exc.status_code, fallback)
        body = ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump()
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Render request validation failures without echoing input values.

        Args:
            _request: Incoming request (unused; required by the handler signature).
            exc: Validation error raised by FastAPI.

        Returns:
            JSON response with locations and messages but no raw inputs.
        """
        errors = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in exc.errors()
        ]
        detail = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details={"errors": errors},
        )
        return JSONResponse(status_code=422, content=ErrorResponse(error=detail).model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Log unexpected errors and hide their details from clients.

        Args:
            request: Incoming request, used only for method and path logging.
            exc: Unexpected exception (logged, never returned).

        Returns:
            Generic 500 JSON response with no internal details.
        """
        logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
        detail = ErrorDetail(code="INTERNAL_ERROR", message="An unexpected error occurred.")
        return JSONResponse(status_code=500, content=ErrorResponse(error=detail).model_dump())
