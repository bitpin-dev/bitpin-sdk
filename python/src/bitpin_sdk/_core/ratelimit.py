"""Client-side sliding-window rate limiter. Pure: it computes delays, the client sleeps.

The server enforces its own limits; this only keeps a well-behaved client under them.
``reserve()`` books a send time atomically, so concurrent callers queue up behind each
other instead of all waking at the same moment.
"""

from __future__ import annotations

import bisect
import threading
from collections.abc import Callable, Mapping, Sequence

from bitpin_sdk.config import RateLimit


class SlidingWindowLimiter:
    def __init__(self, rules: Mapping[str, RateLimit], clock: Callable[[], float]) -> None:
        self._rules = dict(rules)
        self._clock = clock
        self._calls: dict[str, list[float]] = {name: [] for name in self._rules}
        self._lock = threading.Lock()

    def _prune(self, bucket: str, now: float) -> None:
        window = self._rules[bucket].period_seconds
        calls = self._calls[bucket]
        cut = bisect.bisect_right(calls, now - window)
        del calls[:cut]

    def _earliest(self, buckets: Sequence[str], now: float) -> float:
        """The earliest time >= now at which every bucket has room, counting booked sends."""
        at = now
        for _ in range(len(buckets) + 1):
            moved = False
            for bucket in buckets:
                rule = self._rules.get(bucket)
                if rule is None:
                    continue
                calls = self._calls[bucket]
                window = rule.period_seconds
                inside = len(calls) - bisect.bisect_right(calls, at - window)
                if inside >= rule.limit:
                    at = max(at, calls[len(calls) - rule.limit] + window)
                    moved = True
            if not moved:
                break
        return at

    def delay(self, buckets: Sequence[str]) -> float:
        """Seconds to wait before a request that consumes ``buckets``; 0 when it can go now."""
        with self._lock:
            now = self._clock()
            for bucket in buckets:
                if bucket in self._rules:
                    self._prune(bucket, now)
            return self._earliest(buckets, now) - now

    def record(self, buckets: Sequence[str]) -> None:
        """Count one request sent now against each bucket."""
        with self._lock:
            now = self._clock()
            for bucket in buckets:
                if bucket in self._rules:
                    self._prune(bucket, now)
                    bisect.insort(self._calls[bucket], now)

    def reserve(self, buckets: Sequence[str]) -> float:
        """Book the next free send time for ``buckets`` and return the seconds to wait for it."""
        with self._lock:
            now = self._clock()
            for bucket in buckets:
                if bucket in self._rules:
                    self._prune(bucket, now)
            at = self._earliest(buckets, now)
            for bucket in buckets:
                if bucket in self._rules:
                    bisect.insort(self._calls[bucket], at)
            return at - now
