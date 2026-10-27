"""Client-side sliding-window limiter, driven by a fake clock."""

from __future__ import annotations

from bitpin_sdk._core.ratelimit import SlidingWindowLimiter
from bitpin_sdk.config import RateLimit


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_free_bucket_has_no_delay() -> None:
    limiter = SlidingWindowLimiter({"auth": RateLimit(3, "min")}, Clock())
    assert limiter.delay(["auth"]) == 0.0


def test_fourth_call_waits_until_oldest_leaves_window() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter({"auth": RateLimit(3, "min")}, clock)
    for step in (0.0, 10.0, 20.0):
        clock.now = 1000.0 + step
        assert limiter.delay(["auth"]) == 0.0
        limiter.record(["auth"])
    clock.now = 1030.0
    assert limiter.delay(["auth"]) == 30.0
    clock.now = 1060.0
    assert limiter.delay(["auth"]) == 0.0


def test_two_buckets_use_the_longest_delay() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter({"a": RateLimit(1, "sec"), "b": RateLimit(1, "min")}, clock)
    limiter.record(["a", "b"])
    assert limiter.delay(["a", "b"]) == 60.0
    assert limiter.delay(["a"]) == 1.0


def test_unknown_bucket_is_ignored() -> None:
    limiter = SlidingWindowLimiter({}, Clock())
    limiter.record(["x"])
    assert limiter.delay(["x"]) == 0.0


def test_old_entries_are_pruned() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter({"a": RateLimit(2, "sec")}, clock)
    limiter.record(["a"])
    limiter.record(["a"])
    clock.now += 5
    limiter.record(["a"])
    assert limiter.delay(["a"]) == 0.0
    assert len(limiter._calls["a"]) == 1
