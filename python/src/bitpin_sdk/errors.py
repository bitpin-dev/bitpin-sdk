"""Exceptions raised by the SDK. The hierarchy follows ccxt so existing handlers keep working.

BitpinError
├── ExchangeError                 the server answered with an error
│   ├── AuthenticationError       bad key/secret, IP not allowed, token expired or revoked
│   ├── PermissionDenied          account not allowed (e.g. KYC level too low)
│   ├── InsufficientFunds
│   ├── InvalidOrder              rejected order or cancel
│   ├── OrderNotFound
│   ├── BadRequest                invalid parameters
│   │   ├── BadSymbol
│   │   └── InvalidOTP            withdrawal OTP rejected; see ``code``
│   └── NotSupported              Bitpin doesn't offer this yet
└── NetworkError                  the request may not have reached the server
    ├── RateLimitExceeded         see ``retry_after``
    ├── RequestTimeout
    └── ExchangeNotAvailable      5xx / maintenance
"""

from __future__ import annotations

from typing import Any


class BitpinError(Exception):
    """Base class for every SDK error."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: Any = None,
        endpoint_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.endpoint_id = endpoint_id


class ExchangeError(BitpinError):
    pass


class AuthenticationError(ExchangeError):
    pass


class PermissionDenied(ExchangeError):
    pass


class InsufficientFunds(ExchangeError):
    pass


class InvalidOrder(ExchangeError):
    pass


class OrderNotFound(ExchangeError):
    pass


class BadRequest(ExchangeError):
    pass


class BadSymbol(BadRequest):
    pass


class InvalidOTP(BadRequest):
    """The withdrawal OTP was rejected. ``code`` is ``invalid_otp``, ``otp1_already_verified``
    or ``extra_try`` (too many attempts; the withdrawal is cancelled)."""

    def __init__(self, message: str, *, code: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.code = code


class NotSupported(ExchangeError):
    """Bitpin doesn't offer this feature yet. ``feature`` is the ccxt capability name."""

    def __init__(self, message: str, *, feature: str, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.feature = feature


class NetworkError(BitpinError):
    pass


class RateLimitExceeded(NetworkError):
    """HTTP 429. ``retry_after`` is the server's hint in seconds, when it gives one."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class RequestTimeout(NetworkError):
    pass


class ExchangeNotAvailable(NetworkError):
    pass


__all__ = [
    "AuthenticationError",
    "BadRequest",
    "BadSymbol",
    "BitpinError",
    "ExchangeError",
    "ExchangeNotAvailable",
    "InsufficientFunds",
    "InvalidOTP",
    "InvalidOrder",
    "NetworkError",
    "NotSupported",
    "OrderNotFound",
    "PermissionDenied",
    "RateLimitExceeded",
    "RequestTimeout",
]
