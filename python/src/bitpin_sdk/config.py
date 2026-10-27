"""Client configuration. Defaults come from spec/bitpin.yaml; every value can be overridden."""

from __future__ import annotations

import dataclasses
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from bitpin_sdk._generated.spec import RATE_LIMITS, URLS

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

Period = Literal["sec", "min", "hour", "day"]
_PERIOD_SECONDS: dict[str, int] = {"sec": 1, "min": 60, "hour": 3600, "day": 86400}


@dataclass(frozen=True)
class RateLimit:
    """At most ``limit`` requests per ``period``."""

    limit: int
    period: Period

    def __post_init__(self) -> None:
        if self.limit < 1 or self.period not in _PERIOD_SECONDS:
            raise ValueError(f"invalid rate limit {self.limit}/{self.period}")

    @property
    def period_seconds(self) -> int:
        return _PERIOD_SECONDS[self.period]

    @classmethod
    def parse(cls, value: str | RateLimit) -> RateLimit:
        """Accept ``RateLimit`` or a string such as ``"10800/min"``."""
        if isinstance(value, RateLimit):
            return value
        limit, sep, period = value.partition("/")
        if not sep or not limit.isdigit() or period not in _PERIOD_SECONDS or int(limit) < 1:
            raise ValueError(
                f"invalid rate limit {value!r}; use '<count>/<sec|min|hour|day>', e.g. '60/min'"
            )
        return cls(int(limit), cast(Period, period))


def _normalize_rate_limits(raw: Mapping[str, str | RateLimit]) -> dict[str, RateLimit]:
    result: dict[str, RateLimit] = {}
    for name, value in raw.items():
        if name not in RATE_LIMITS:
            known = ", ".join(sorted(RATE_LIMITS))
            raise ValueError(f"unknown rate-limit bucket {name!r}; known buckets: {known}")
        result[name] = RateLimit.parse(value)
    return result


@dataclass(frozen=True)
class Config:
    """Settings for ``Bitpin`` and ``AsyncBitpin``.

    ``rate_limits`` overrides the server defaults per bucket, e.g. a VIP's real limit:
    ``Config(rate_limits={"orderbook": "10800/min"})``. See docs/en/rate-limits.md.
    """

    api_key: str | None = field(default=None, repr=False)
    secret_key: str | None = field(default=None, repr=False)
    rest_url: str = URLS["rest"]
    ws_url: str = URLS["ws"]
    timeout: float = 10.0
    max_retries: int = 3
    enable_rate_limit: bool = True
    rate_limits: Mapping[str, str | RateLimit] = field(default_factory=dict)
    user_agent: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rate_limits", _normalize_rate_limits(self.rate_limits))
        object.__setattr__(self, "timeout", float(self.timeout))
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

    def __repr__(self) -> str:
        shown = {f.name: getattr(self, f.name) for f in dataclasses.fields(self) if f.repr}
        secrets = {
            "api_key": "***" if self.api_key else None,
            "secret_key": "***" if self.secret_key else None,
        }
        body = ", ".join(f"{k}={v!r}" for k, v in {**secrets, **shown}.items())
        return f"Config({body})"

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def rate_limit(self, bucket: str) -> RateLimit:
        """The effective limit of a bucket: the user's override, else the server default."""
        override = self.rate_limits.get(bucket)
        if override is not None:
            return cast(RateLimit, override)
        limit, period = RATE_LIMITS[bucket]
        return RateLimit(limit, period)

    def all_rate_limits(self) -> dict[str, RateLimit]:
        return {name: self.rate_limit(name) for name in RATE_LIMITS}

    def replace(self, **changes: Any) -> Config:
        return dataclasses.replace(self, **changes)

    @classmethod
    def _from_mapping(cls, data: Mapping[str, Any]) -> Config:
        names = {f.name for f in dataclasses.fields(cls)}
        for key in data:
            if key not in names:
                raise ValueError(
                    f"unknown config key {key!r}; known keys: {', '.join(sorted(names))}"
                )
        return cls(**dict(data))

    @classmethod
    def from_ccxt(cls, options: Mapping[str, Any]) -> Config:
        """Build from a ccxt-style dict: ``{"apiKey", "secret", "timeout" (ms), "enableRateLimit",
        "options": {"rateLimits": {...}}}``."""
        kwargs: dict[str, Any] = {}
        if "apiKey" in options:
            kwargs["api_key"] = options["apiKey"]
        if "secret" in options:
            kwargs["secret_key"] = options["secret"]
        if "timeout" in options:
            kwargs["timeout"] = float(options["timeout"]) / 1000
        if "enableRateLimit" in options:
            kwargs["enable_rate_limit"] = bool(options["enableRateLimit"])
        if "userAgent" in options:
            kwargs["user_agent"] = options["userAgent"]
        extra = options.get("options") or {}
        if "rateLimits" in extra:
            kwargs["rate_limits"] = extra["rateLimits"]
        return cls(**kwargs)

    @classmethod
    def from_file(cls, path: str | Path) -> Config:
        """Read the ``[bitpin]`` table of a TOML file."""
        with Path(path).open("rb") as fh:
            data = tomllib.load(fh)
        return cls._from_mapping(data.get("bitpin", {}))

    @classmethod
    def from_env(cls, **overrides: Any) -> Config:
        """Read ``BITPIN_API_KEY`` and ``BITPIN_SECRET_KEY``; keyword arguments set the rest."""
        return cls(
            api_key=os.environ.get("BITPIN_API_KEY"),
            secret_key=os.environ.get("BITPIN_SECRET_KEY"),
            **overrides,
        )

    @classmethod
    def coerce(cls, value: Config | Mapping[str, Any] | None) -> Config:
        """Accept a ``Config``, a ccxt-style dict, a dict of ``Config`` fields, or ``None``."""
        if value is None:
            return cls()
        if isinstance(value, Config):
            return value
        if any(key in value for key in ("apiKey", "secret", "enableRateLimit", "options")):
            return cls.from_ccxt(value)
        return cls._from_mapping(value)
