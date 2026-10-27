"""Token lifecycle: when to authenticate, when to refresh, how JWT expiry is read."""

from __future__ import annotations

import base64
import json

from bitpin_sdk._core.auth import Tokens, TokenState, jwt_exp


def make_jwt(payload: dict[str, object]) -> str:
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    return f"{b64(b'{}')}.{b64(json.dumps(payload).encode())}.sig"


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_jwt_exp_reads_payload() -> None:
    assert jwt_exp(make_jwt({"exp": 1234})) == 1234.0


def test_jwt_exp_malformed_is_none() -> None:
    assert jwt_exp("not-a-jwt") is None
    assert jwt_exp("a.!!!.c") is None
    assert jwt_exp(make_jwt({"no": "exp"})) is None
    assert jwt_exp(make_jwt({"exp": "soon"})) is None


def test_no_tokens_means_authenticate() -> None:
    assert TokenState(Clock()).action() == "authenticate"


def test_fresh_tokens_are_ok() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.set_tokens(
        {
            "access": make_jwt({"exp": clock.now + 900}),
            "refresh": make_jwt({"exp": clock.now + 86400}),
        }
    )
    assert state.action() == "ok"
    assert state.access_token is not None


def test_refresh_two_minutes_before_expiry() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.set_tokens(
        {
            "access": make_jwt({"exp": clock.now + 900}),
            "refresh": make_jwt({"exp": clock.now + 86400}),
        }
    )
    clock.now += 900 - 121
    assert state.action() == "ok"
    clock.now += 1
    assert state.action() == "refresh"


def test_expired_refresh_means_authenticate() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.set_tokens(
        {
            "access": make_jwt({"exp": clock.now + 900}),
            "refresh": make_jwt({"exp": clock.now + 1000}),
        }
    )
    clock.now += 1000
    assert state.action() == "authenticate"


def test_set_access_keeps_refresh() -> None:
    clock = Clock()
    state = TokenState(clock)
    refresh = make_jwt({"exp": clock.now + 86400})
    state.set_tokens({"access": make_jwt({"exp": clock.now + 10}), "refresh": refresh})
    assert state.action() == "refresh"
    state.set_access({"access": make_jwt({"exp": clock.now + 900})})
    assert state.action() == "ok"
    assert state.tokens is not None
    assert state.tokens.refresh == refresh


def test_missing_exp_falls_back_to_spec_ttl() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.set_tokens({"access": "opaque", "refresh": "opaque2"})
    assert state.tokens == Tokens("opaque", "opaque2", clock.now + 900, clock.now + 2592000)


def test_clear() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.set_tokens({"access": "a", "refresh": "r"})
    state.clear()
    assert state.action() == "authenticate"
    assert state.access_token is None


def test_load_restores_tokens() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.load(Tokens("a", "r", clock.now + 900, clock.now + 9000))
    assert state.action() == "ok"


def test_tokens_repr_hides_values() -> None:
    text = repr(Tokens("ACCESS-SECRET", "REFRESH-SECRET", 1.0, 2.0))
    assert "ACCESS-SECRET" not in text
    assert "REFRESH-SECRET" not in text


def test_expire_access_forces_refresh() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.set_tokens(
        {
            "access": make_jwt({"exp": clock.now + 900}),
            "refresh": make_jwt({"exp": clock.now + 86400}),
        }
    )
    state.expire_access()
    assert state.action() == "refresh"
    TokenState(clock).expire_access()


def test_expire_access_ignores_a_stale_token() -> None:
    clock = Clock()
    state = TokenState(clock)
    state.set_tokens(
        {
            "access": make_jwt({"exp": clock.now + 900}),
            "refresh": make_jwt({"exp": clock.now + 86400}),
        }
    )
    old = state.access_token
    state.set_access({"access": make_jwt({"exp": clock.now + 1800})})
    state.expire_access(old)
    assert state.action() == "ok"
    state.expire_access(state.access_token)
    assert state.action() == "refresh"


def test_jwt_exp_rejects_non_finite_values() -> None:
    for raw in ('{"exp": NaN}', '{"exp": Infinity}', '{"exp": -Infinity}'):
        payload = base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()
        assert jwt_exp(f"e30.{payload}.sig") is None
