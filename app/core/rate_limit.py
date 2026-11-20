"""In-memory sliding-window rate limiting (buckets live on app.state)."""

from datetime import datetime

from fastapi import Request

from app.core.errors import RateLimitedError


def bucket_key(request: Request) -> str:
    """Build the rate limit bucket key for one request.

    Args:
        request: Incoming request.

    Returns:
        Bucket key combining path and client host.
    """
    host = request.client.host if request.client is not None else "unknown"
    return f"{request.url.path}:{host}"


def check_rate_limit(
    buckets: dict[str, list[float]],
    key: str,
    limit: int,
    window_seconds: float,
    now: datetime,
) -> None:
    """Enforce a sliding-window rate limit for one key.

    Args:
        buckets: Hit timestamps by key (owned by the caller).
        key: Bucket key (for example endpoint plus client).
        limit: Maximum hits per window.
        window_seconds: Window length in seconds.
        now: Current time (injected for deterministic tests).

    Raises:
        RateLimitedError: When the key already used its allowance.
    """
    timestamp = now.timestamp()
    cutoff = timestamp - window_seconds
    hits = [hit for hit in buckets.get(key, []) if hit > cutoff]
    if len(hits) >= limit:
        raise RateLimitedError(details={"limit": limit, "window_seconds": window_seconds})
    hits.append(timestamp)
    buckets[key] = hits
