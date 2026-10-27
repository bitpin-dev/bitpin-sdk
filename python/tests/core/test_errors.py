"""Every HTTP error the server returns maps to one SDK exception class."""

from __future__ import annotations

from typing import Any

import pytest

from bitpin_sdk import errors
from bitpin_sdk._core.errors import map_error, not_supported


@pytest.mark.parametrize(
    ("endpoint_id", "status", "body", "expected"),
    [
        (
            "private_get_wlt_wallets",
            401,
            {"detail": "Given token not valid", "code": "token_not_valid"},
            errors.AuthenticationError,
        ),
        (
            "credentials_post_usr_authenticate",
            406,
            {"detail": "api_credential_wrong"},
            errors.AuthenticationError,
        ),
        (
            "credentials_post_usr_ws_info",
            406,
            {"detail": "wrong ip 1.2.3.4"},
            errors.AuthenticationError,
        ),
        ("private_post_wlt_address", 403, {"detail": "kyc required"}, errors.PermissionDenied),
        ("private_get_odr_orders_id", 404, {"detail": "Not found."}, errors.OrderNotFound),
        ("private_delete_odr_orders_id", 404, {"detail": "Not found."}, errors.OrderNotFound),
        (
            "private_delete_odr_orders_identifier_identifier",
            404,
            {"detail": "Not found."},
            errors.OrderNotFound,
        ),
        ("public_get_mth_orderbook_symbol", 404, {"detail": "Not found."}, errors.BadRequest),
        (
            "private_post_odr_orders",
            406,
            {"detail": "insufficent_balance"},
            errors.InsufficientFunds,
        ),
        (
            "private_post_odr_orders_bulk",
            406,
            {"detail": "insufficent_frozen"},
            errors.InsufficientFunds,
        ),
        (
            "private_post_wlt_withdraws",
            406,
            {"detail": "insufficent_pool_balance"},
            errors.InsufficientFunds,
        ),
        (
            "private_delete_odr_orders_id",
            406,
            {"detail": "Cancel order is not allowed.", "code": "cancel_order_not_allowed"},
            errors.InvalidOrder,
        ),
        (
            "private_delete_odr_orders_identifier_identifier",
            406,
            {"detail": "not allowed"},
            errors.InvalidOrder,
        ),
        (
            "private_post_wlt_withdraws_verify_otp_id",
            400,
            {"detail": "wrong", "code": "invalid_otp"},
            errors.InvalidOTP,
        ),
        (
            "private_post_wlt_withdraws_verify_otp_id",
            400,
            {"code": "otp1_already_verified"},
            errors.InvalidOTP,
        ),
        ("private_post_wlt_withdraws_verify_otp_id", 400, {"code": "extra_try"}, errors.InvalidOTP),
        (
            "private_post_odr_orders",
            400,
            {"price": ["This field is required."]},
            errors.InvalidOrder,
        ),
        (
            "public_get_mkt_candles",
            400,
            {"detail": "Requested 43201 candles exceeds maximum limit of 10000"},
            errors.BadRequest,
        ),
        (
            "private_get_wlt_networks",
            406,
            {"detail": "currency_code is required"},
            errors.ExchangeError,
        ),
        ("public_get_mkt_tickers", 500, "<html>oops</html>", errors.ExchangeNotAvailable),
        ("public_get_mkt_tickers", 502, None, errors.ExchangeNotAvailable),
        ("public_get_mkt_tickers", 503, None, errors.ExchangeNotAvailable),
        ("public_get_mkt_tickers", 504, None, errors.ExchangeNotAvailable),
        ("public_get_mkt_tickers", 418, None, errors.ExchangeError),
    ],
)
def test_map_error(
    endpoint_id: str, status: int, body: Any, expected: type[errors.BitpinError]
) -> None:
    error = map_error(endpoint_id, status, body)
    assert type(error) is expected
    assert error.status == status
    assert error.body == body
    assert error.endpoint_id == endpoint_id


def test_rate_limit_parses_retry_after_from_detail() -> None:
    body = {"detail": "Request was throttled. Expected available in 86398 seconds."}
    error = map_error("public_get_mkt_tickers", 429, body)
    assert isinstance(error, errors.RateLimitExceeded)
    assert error.retry_after == 86398.0


def test_rate_limit_prefers_retry_after_header() -> None:
    error = map_error("public_get_mkt_tickers", 429, {"detail": "x"}, retry_after_header="12")
    assert isinstance(error, errors.RateLimitExceeded)
    assert error.retry_after == 12.0


def test_rate_limit_without_hint_has_no_retry_after() -> None:
    error = map_error("public_get_mkt_tickers", 429, None, retry_after_header="soon")
    assert isinstance(error, errors.RateLimitExceeded)
    assert error.retry_after is None


def test_otp_error_exposes_code() -> None:
    error = map_error("private_post_wlt_withdraws_verify_otp_id", 400, {"code": "extra_try"})
    assert isinstance(error, errors.InvalidOTP)
    assert error.code == "extra_try"


def test_error_message_includes_status_endpoint_and_detail() -> None:
    error = map_error("private_post_odr_orders", 406, {"detail": "insufficent_balance"})
    assert str(error) == "406 private_post_odr_orders: insufficent_balance"


def test_hierarchy_matches_ccxt() -> None:
    assert issubclass(errors.RateLimitExceeded, errors.NetworkError)
    assert issubclass(errors.RequestTimeout, errors.NetworkError)
    assert issubclass(errors.ExchangeNotAvailable, errors.NetworkError)
    assert issubclass(errors.NetworkError, errors.BitpinError)
    for cls in (
        errors.AuthenticationError,
        errors.PermissionDenied,
        errors.InsufficientFunds,
        errors.InvalidOrder,
        errors.OrderNotFound,
        errors.BadRequest,
        errors.NotSupported,
    ):
        assert issubclass(cls, errors.ExchangeError)
    assert issubclass(errors.BadSymbol, errors.BadRequest)
    assert issubclass(errors.InvalidOTP, errors.BadRequest)
    assert issubclass(errors.ExchangeError, errors.BitpinError)


def test_not_supported_message_is_bilingual() -> None:
    error = not_supported("editOrder")
    assert isinstance(error, errors.NotSupported)
    assert "Cancel the order" in str(error)
    assert "ویرایش" in str(error)
    assert error.feature == "editOrder"
