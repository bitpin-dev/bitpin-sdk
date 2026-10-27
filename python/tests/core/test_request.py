from __future__ import annotations

from decimal import Decimal

import pytest

from bitpin_sdk._core.request import build_request
from bitpin_sdk.config import Config

CONFIG = Config()


def test_get_puts_params_in_query_and_drops_none() -> None:
    req = build_request(
        CONFIG,
        "private_get_odr_orders",
        params={"symbol": "BTC_IRT", "state": ["active", "initial"], "limit": 50, "side": None},
    )
    assert req.method == "GET"
    assert req.url == "https://api.bitpin.org/api/v1/odr/orders/"
    assert req.params == {"symbol": "BTC_IRT", "state": "active,initial", "limit": "50"}
    assert req.json is None
    assert req.auth == "private"
    assert req.buckets == ("order_read",)
    assert req.idempotent is True


def test_query_bools_are_lowercase() -> None:
    req = build_request(
        CONFIG, "public_get_mkt_networks", params={"can_deposit": True, "can_withdraw": False}
    )
    assert req.params == {"can_deposit": "true", "can_withdraw": "false"}


def test_post_body_formats_decimals_as_plain_strings() -> None:
    req = build_request(
        CONFIG,
        "private_post_odr_orders",
        body={
            "symbol": "BTC_IRT",
            "base_amount": Decimal("1E-8"),
            "price": 3100000000,
            "stop_price": None,
            "nested": [{"a": 0.1}],
        },
    )
    assert req.json == {
        "symbol": "BTC_IRT",
        "base_amount": "0.00000001",
        "price": "3100000000",
        "nested": [{"a": "0.1"}],
    }
    assert req.params is None
    assert req.idempotent is False


def test_bools_in_body_stay_bools() -> None:
    req = build_request(
        CONFIG,
        "private_post_wlt_withdraws_verify_otp_id",
        path_params={"id": 7},
        body={"otp": "123456", "is_second_otp": False},
    )
    assert req.json == {"otp": "123456", "is_second_otp": False}
    assert req.url.endswith("/api/v1/wlt/withdraws/verify/otp/7/")


def test_bulk_body_can_be_a_list() -> None:
    req = build_request(CONFIG, "private_post_odr_orders_bulk", body=[{"price": Decimal("1.50")}])
    assert req.json == [{"price": "1.5"}]
    assert req.buckets == ("order_bulk_create", "order_bulk_cancel")


def test_path_params_are_url_encoded() -> None:
    req = build_request(
        CONFIG,
        "private_delete_odr_orders_identifier_identifier",
        path_params={"identifier": "a b/c"},
    )
    assert req.url == "https://api.bitpin.org/api/v1/odr/orders/identifier/a%20b%2Fc/"


def test_missing_path_param_raises() -> None:
    with pytest.raises(ValueError, match="missing path parameter 'symbol'"):
        build_request(CONFIG, "public_get_mth_orderbook_symbol")


def test_unknown_endpoint_raises() -> None:
    with pytest.raises(KeyError):
        build_request(CONFIG, "public_get_nope")


def test_custom_rest_url() -> None:
    req = build_request(Config(rest_url="https://api.bitpin.market/"), "public_get_mkt_tickers")
    assert req.url == "https://api.bitpin.market/api/v1/mkt/tickers/"
