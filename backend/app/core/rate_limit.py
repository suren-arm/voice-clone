"""In-process token-bucket rate limiting.

Deliberately not Redis. The MVP is a single API process in front of a single
GPU, so a dict of buckets is correct *and* has no operational cost. The moment
a second replica exists this becomes wrong -- the swap to a shared store is
documented in ``docs/ARCHITECTURE.md`` and touches only this file.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from fastapi import Request

from app.core.errors import RateLimitedError


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


@dataclass
class RateLimiter:
    """Token bucket: ``capacity`` requests, refilled over ``window_seconds``."""

    capacity: int
    window_seconds: float
    name: str = "requests"
    _buckets: dict[str, _Bucket] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _last_sweep: float = field(default=0.0, repr=False)

    def check(self, key: str, *, cost: float = 1.0) -> None:
        """Consume ``cost`` tokens for ``key`` or raise :class:`RateLimitedError`."""
        now = time.monotonic()
        refill_rate = self.capacity / self.window_seconds
        with self._lock:
            self._sweep(now)
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.capacity), updated_at=now)
                self._buckets[key] = bucket
            else:
                elapsed = now - bucket.updated_at
                bucket.tokens = min(self.capacity, bucket.tokens + elapsed * refill_rate)
                bucket.updated_at = now

            if bucket.tokens < cost:
                deficit = cost - bucket.tokens
                retry_after = max(1, int(deficit / refill_rate) + 1)
                raise RateLimitedError(
                    f"Too many {self.name}. Try again in {retry_after}s.",
                    retry_after=retry_after,
                    details={"limit": self.capacity, "window_seconds": int(self.window_seconds)},
                )
            bucket.tokens -= cost

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def _sweep(self, now: float) -> None:
        """Drop fully-refilled buckets so the dict cannot grow without bound."""
        if now - self._last_sweep < 60.0:
            return
        self._last_sweep = now
        stale = now - self.window_seconds * 2
        for key in [k for k, b in self._buckets.items() if b.updated_at < stale]:
            del self._buckets[key]


def client_key(request: Request) -> str:
    """Identify the caller for rate-limiting purposes.

    Uses the peer address. ``X-Forwarded-For`` is intentionally *not* trusted:
    it is client-controlled unless a known proxy sets it, and trusting it blindly
    turns the limiter off. Behind a real proxy, run uvicorn with
    ``--proxy-headers --forwarded-allow-ips=<proxy ip>`` so Starlette rewrites
    ``request.client`` for us.

    When authentication arrives (Phase 2) this becomes the user ID.
    """
    return request.client.host if request.client else "unknown"
