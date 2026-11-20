"""Sliding-window rate limiter behaviour."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import RateLimitedError
from app.core.rate_limit import check_rate_limit

NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)


def test_allows_hits_within_limit() -> None:
    """Allow hits up to the limit."""
    buckets: dict[str, list[float]] = {}
    check_rate_limit(buckets, "key", 2, 60.0, NOW)
    check_rate_limit(buckets, "key", 2, 60.0, NOW + timedelta(seconds=1))


def test_blocks_hits_past_limit() -> None:
    """Reject the hit that exceeds the limit."""
    buckets: dict[str, list[float]] = {}
    check_rate_limit(buckets, "key", 1, 60.0, NOW)
    with pytest.raises(RateLimitedError) as caught:
        check_rate_limit(buckets, "key", 1, 60.0, NOW + timedelta(seconds=1))
    assert caught.value.details == {"limit": 1, "window_seconds": 60.0}


def test_window_slides_with_time() -> None:
    """Forget hits that fall outside the window."""
    buckets: dict[str, list[float]] = {}
    check_rate_limit(buckets, "key", 1, 60.0, NOW)
    check_rate_limit(buckets, "key", 1, 60.0, NOW + timedelta(seconds=61))


def test_boundary_hits_expire() -> None:
    """Expire hits exactly at the window edge."""
    buckets: dict[str, list[float]] = {}
    check_rate_limit(buckets, "key", 1, 60.0, NOW)
    check_rate_limit(buckets, "key", 1, 60.0, NOW + timedelta(seconds=60))


def test_keys_stay_isolated() -> None:
    """Track each key in its own bucket."""
    buckets: dict[str, list[float]] = {}
    check_rate_limit(buckets, "first", 1, 60.0, NOW)
    check_rate_limit(buckets, "second", 1, 60.0, NOW)
    with pytest.raises(RateLimitedError):
        check_rate_limit(buckets, "first", 1, 60.0, NOW)
