"""Injectable clock helpers (all timestamps are UTC)."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current UTC time with timezone information attached.
    """
    return datetime.now(UTC)
