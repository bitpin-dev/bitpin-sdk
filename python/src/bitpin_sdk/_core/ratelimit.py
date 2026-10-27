"""Client-side sliding-window rate limiter. Pure: it computes delays, the client sleeps.

The server enforces its own limits; this only keeps a well-behaved client under them.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence

from bitpin_sdk.config import RateLimit


class SlidingWindowLimiter:
    def __init__(self, rules: Mapping[str, RateLimit], clock: Callable[[], float]) -> None:
        self._rules = dict(rules)
        self._clock = clock
        self._calls: dict[str, deque[float]] = {name: deque() for name in self._rules}

    def _prune(self, bucket: str, now: float) -> None:
        window = self._rules[bucket].period_seconds
        calls = self._calls[bucket]
        while calls and calls[0] <= now - window:
            calls.popleft()

    def delay(self, buckets: Sequence[str]) -> float:
        """Seconds to wait before a request that consumes ``buckets``; 0 when it can go now."""
        now = self._clock()
        wait = 0.0
        for bucket in buckets:
            rule = self._rules.get(bucket)
            if rule is None:
                continue
            self._prune(bucket, now)
            calls = self._calls[bucket]
            if len(calls) >= rule.limit:
                oldest = calls[len(calls) - rule.limit]
                wait = max(wait, oldest + rule.period_seconds - now)
        return wait

    def record(self, buckets: Sequence[str]) -> None:
        """Count one request against each bucket."""
        now = self._clock()
        for bucket in buckets:
            if bucket in self._rules:
                self._prune(bucket, now)
                self._calls[bucket].append(now)
