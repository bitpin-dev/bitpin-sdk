"""Access/refresh token lifecycle. Pure: decides what to do, the client does the network call.

Authenticate is limited to 3 requests per minute per IP, so tokens are cached and the
access token is refreshed shortly before it expires instead of re-authenticating.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from bitpin_sdk._generated.spec import CONSTANTS

Action = Literal["ok", "refresh", "authenticate"]


@dataclass(frozen=True)
class Tokens:
    access: str = field(repr=False)
    refresh: str = field(repr=False)
    access_exp: float
    refresh_exp: float


def jwt_exp(token: str) -> float | None:
    """The ``exp`` claim of a JWT, read without verifying the signature; None if unreadable."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, ValueError):
        return None
    exp = claims.get("exp") if isinstance(claims, dict) else None
    if isinstance(exp, (int, float)) and not isinstance(exp, bool):
        return float(exp)
    return None


class TokenState:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self.tokens: Tokens | None = None

    @property
    def access_token(self) -> str | None:
        return self.tokens.access if self.tokens else None

    def action(self) -> Action:
        if self.tokens is None:
            return "authenticate"
        now = self._clock()
        if now >= self.tokens.refresh_exp:
            return "authenticate"
        if now >= self.tokens.access_exp - CONSTANTS["token_refresh_margin_seconds"]:
            return "refresh"
        return "ok"

    def _exp(self, token: str, ttl_key: str) -> float:
        exp = jwt_exp(token)
        return exp if exp is not None else self._clock() + CONSTANTS[ttl_key]

    def set_tokens(self, data: Mapping[str, Any]) -> Tokens:
        """Store the ``{"access", "refresh"}`` pair returned by authenticate."""
        access, refresh = str(data["access"]), str(data["refresh"])
        self.tokens = Tokens(
            access,
            refresh,
            self._exp(access, "access_token_ttl_seconds"),
            self._exp(refresh, "refresh_token_ttl_seconds"),
        )
        return self.tokens

    def set_access(self, data: Mapping[str, Any]) -> Tokens:
        """Store the ``{"access"}`` returned by refresh; the refresh token is not rotated."""
        if self.tokens is None:
            raise RuntimeError("set_access() called before set_tokens()")
        access = str(data["access"])
        self.tokens = Tokens(
            access,
            self.tokens.refresh,
            self._exp(access, "access_token_ttl_seconds"),
            self.tokens.refresh_exp,
        )
        return self.tokens

    def expire_access(self) -> None:
        """Mark the access token unusable (server said 401) so the next call refreshes it."""
        if self.tokens is not None:
            self.tokens = Tokens(
                self.tokens.access, self.tokens.refresh, 0.0, self.tokens.refresh_exp
            )

    def load(self, tokens: Tokens) -> None:
        self.tokens = tokens

    def clear(self) -> None:
        self.tokens = None
