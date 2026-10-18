"""Fixed-window rate limiter for the partner API (NA-05) and authentication (NA-06).

In-process: correct for the single API instance we run today. When the stack gets Redis (BU-02/BU-04), move
the counters there so every instance shares them; the `hit` interface stays the same."""

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after: int  # whole seconds until the window resets

    def headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_after),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.reset_after)
        return headers


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}  # bucket -> (window start, requests in it)

    def hit(self, bucket: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Count one request against `bucket` and say whether it is allowed."""
        now = self._clock()
        with self._lock:
            start, count = self._windows.get(bucket, (now, 0))
            if now - start >= window_seconds:
                start, count = now, 0
            allowed = count < limit
            if allowed:
                count += 1
            self._windows[bucket] = (start, count)
            if len(self._windows) > 10_000:  # forget long-idle buckets so memory stays bounded
                self._windows = {b: w for b, w in self._windows.items() if now - w[0] < window_seconds}
        reset_after = max(1, math.ceil(start + window_seconds - now))
        return RateLimitResult(allowed=allowed, limit=limit, remaining=max(0, limit - count), reset_after=reset_after)

    def peek(self, bucket: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Like `hit`, without counting: is `bucket` already over its limit?"""
        now = self._clock()
        with self._lock:
            start, count = self._windows.get(bucket, (now, 0))
        if now - start >= window_seconds:
            start, count = now, 0
        reset_after = max(1, math.ceil(start + window_seconds - now))
        return RateLimitResult(allowed=count < limit, limit=limit, remaining=max(0, limit - count), reset_after=reset_after)

    def clear(self, bucket: str) -> None:
        with self._lock:
            self._windows.pop(bucket, None)

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


partner_limiter = RateLimiter()
auth_limiter = RateLimiter()  # login, signup and password checks (NA-06)
