"""Token-bucket behaviour."""

import pytest

from app.core.errors import RateLimitedError
from app.core.rate_limit import RateLimiter


def test_allows_up_to_capacity():
    limiter = RateLimiter(capacity=3, window_seconds=60)
    for _ in range(3):
        limiter.check("client-a")
    with pytest.raises(RateLimitedError):
        limiter.check("client-a")


def test_buckets_are_per_key():
    limiter = RateLimiter(capacity=1, window_seconds=60)
    limiter.check("a")
    limiter.check("b")  # different key, still has its own tokens
    with pytest.raises(RateLimitedError):
        limiter.check("a")


def test_refills_over_time(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: clock["now"])

    limiter = RateLimiter(capacity=2, window_seconds=10)
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(RateLimitedError):
        limiter.check("a")

    clock["now"] += 5.1  # half a window -> one token back
    limiter.check("a")


def test_error_carries_retry_after():
    limiter = RateLimiter(capacity=1, window_seconds=60)
    limiter.check("a")
    with pytest.raises(RateLimitedError) as excinfo:
        limiter.check("a")
    assert excinfo.value.retry_after >= 1
    assert excinfo.value.status_code == 429
