"""Structured JSON logging with request-id correlation."""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("awwal.request")

# Request-scoped correlation id. ContextVar keeps each request isolated even
# when concurrent requests share this process.
_request_id: ContextVar[str] = ContextVar("awwal_request_id", default="-")


def get_request_id() -> str:
    """Return the request id for the current context.

    Returns:
        The active request id, or ``-`` when outside a request.
    """
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Render one log record as a single JSON line.

        Args:
            record: Record to render.

        Returns:
            The record encoded as single-line JSON.
        """
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        extras = record.__dict__
        for key in ("method", "path", "status_code", "duration_ms"):
            if key in extras:
                payload[key] = extras[key]
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure root JSON logging to stdout.

    Args:
        level: Root log level name.

    Raises:
        ValueError: If the level name is unknown.
    """
    level_name = level.upper()
    if level_name not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        raise ValueError(f"Unknown log level: {level}.")
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level_name)


class RequestIdMiddleware:
    """Assign request ids, echo them, and log each HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        """Store the downstream ASGI application.

        Args:
            app: Downstream ASGI application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI message cycle with request-id context.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive channel.
            send: ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers: dict[bytes, bytes] = dict(scope.get("headers", []))
        raw_value: bytes = headers.get(b"x-request-id", b"")
        incoming = raw_value.decode("latin-1").strip()
        request_id = incoming[:64] if incoming else uuid.uuid4().hex
        token = _request_id.set(request_id)
        method: str = scope.get("method", "")
        path: str = scope.get("path", "")
        status_code = 500
        started = time.perf_counter()

        async def sender(message: Message) -> None:
            """Capture the status code and echo the request id.

            Args:
                message: Outgoing ASGI message to inspect and forward.
            """
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers: list[tuple[bytes, bytes]] = list(message["headers"])
                response_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, sender)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
            logger.info(
                "request completed",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            _request_id.reset(token)
