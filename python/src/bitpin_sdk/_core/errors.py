"""Map an HTTP error response to an SDK exception, using the rules in the spec."""

from __future__ import annotations

import json
import re
from typing import Any

from bitpin_sdk import errors
from bitpin_sdk._generated.spec import ERROR_RULES, NOT_SUPPORTED

_RETRY_AFTER = re.compile(r"available in (\d+(?:\.\d+)?) second", re.IGNORECASE)
_OTP_CODES = ("invalid_otp", "otp1_already_verified", "extra_try")

_CLASSES: dict[str, type[errors.BitpinError]] = {
    name: getattr(errors, name)
    for name in (
        "ExchangeError",
        "AuthenticationError",
        "PermissionDenied",
        "InsufficientFunds",
        "InvalidOrder",
        "OrderNotFound",
        "BadRequest",
        "InvalidOTP",
        "RateLimitExceeded",
        "ExchangeNotAvailable",
    )
}


def _body_text(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    return json.dumps(body, ensure_ascii=False)


def _detail(body: Any) -> str:
    if isinstance(body, dict):
        for key in ("detail", "code", "message"):
            if isinstance(body.get(key), str):
                return str(body[key])
    text = _body_text(body)
    return text[:200]


def _retry_after(body: Any, header: str | None) -> float | None:
    if header is not None:
        try:
            return float(header)
        except ValueError:
            pass
    match = _RETRY_AFTER.search(_body_text(body))
    return float(match.group(1)) if match else None


def map_error(
    endpoint_id: str, status: int, body: Any, *, retry_after_header: str | None = None
) -> errors.BitpinError:
    """Return the exception for an error response. The caller raises it."""
    text = _body_text(body).lower()
    name = "ExchangeError"
    for rule in ERROR_RULES:
        if rule.status != status:
            continue
        if rule.paths and not any(endpoint_id.startswith(p) for p in rule.paths):
            continue
        if rule.detail and not any(d.lower() in text for d in rule.detail):
            continue
        name = rule.error
        break

    detail = _detail(body)
    message = f"{status} {endpoint_id}: {detail}" if detail else f"{status} {endpoint_id}"
    common: dict[str, Any] = {"status": status, "body": body, "endpoint_id": endpoint_id}
    if name == "RateLimitExceeded":
        return errors.RateLimitExceeded(
            message, retry_after=_retry_after(body, retry_after_header), **common
        )
    if name == "InvalidOTP":
        code = next((c for c in _OTP_CODES if c in text), None)
        return errors.InvalidOTP(message, code=code, **common)
    return _CLASSES[name](message, **common)


def not_supported(feature: str) -> errors.NotSupported:
    """The NotSupported error for a ccxt capability Bitpin doesn't offer, in English and Persian."""
    en, fa = NOT_SUPPORTED[feature]
    return errors.NotSupported(f"{en}\n{fa}", feature=feature)
