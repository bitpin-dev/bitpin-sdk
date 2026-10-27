"""The examples run against mocked HTTP and never write without --live."""

from __future__ import annotations

import asyncio
import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import respx

from tests.conftest import route

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "python"
WRITES = {"POST", "DELETE"}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("BITPIN_API_KEY", "test-key")
    monkeypatch.setenv("BITPIN_SECRET_KEY", "test-secret")
    monkeypatch.syspath_prepend(str(EXAMPLES))
    yield
    for name in list(sys.modules):
        if name in {
            "_common",
            "quickstart",
            "place_and_cancel",
            "bulk_orders",
            "market_maker",
            "withdraw_with_otp",
            "stream_orderbook",
        }:
            del sys.modules[name]


def load(name: str) -> ModuleType:
    return importlib.import_module(name)


def writes(mock: respx.MockRouter) -> list[str]:
    return [
        f"{c.request.method} {c.request.url.path}"
        for c in mock.calls
        if c.request.method in WRITES and "/usr/" not in c.request.url.path
    ]


def mock_market_data(mock: respx.MockRouter) -> None:
    for endpoint in (
        "public_get_mkt_markets",
        "public_get_mkt_tickers",
        "private_get_wlt_wallets",
        "credentials_post_usr_authenticate",
    ):
        route(mock, endpoint)
    route(mock, "public_get_mth_orderbook_symbol")


def test_quickstart(mock: respx.MockRouter, capsys: pytest.CaptureFixture[str]) -> None:
    mock_market_data(mock)
    assert load("quickstart").main(["--symbol", "BTC/IRT"]) == 0
    out = capsys.readouterr().out
    assert "3 markets" in out
    assert "non-zero balances" in out
    assert writes(mock) == []


@pytest.mark.parametrize(
    ("name", "argv"),
    [
        ("place_and_cancel", ["--price", "90000", "--amount", "10"]),
        ("bulk_orders", ["--top", "90000", "--step", "100", "--count", "3", "--amount", "10"]),
        (
            "withdraw_with_otp",
            ["--currency", "USDT", "--network", "TRX", "--address", "TTest", "--amount", "1"],
        ),
    ],
)
def test_write_examples_are_dry_run_by_default(
    name: str, argv: list[str], mock: respx.MockRouter, capsys: pytest.CaptureFixture[str]
) -> None:
    assert load(name).main(argv) == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert mock.calls.call_count == 0


def test_place_and_cancel_live(mock: respx.MockRouter) -> None:
    route(mock, "credentials_post_usr_authenticate")
    route(mock, "private_post_odr_orders")
    route(mock, "private_get_odr_orders_id", id="535179385")
    route(mock, "private_delete_odr_orders_identifier_identifier")
    assert load("place_and_cancel").main(["--price", "90000", "--amount", "10", "--live"]) == 0
    assert writes(mock)[0] == "POST /api/v1/odr/orders/"
    assert writes(mock)[1].startswith("DELETE /api/v1/odr/orders/identifier/example-")


def test_bulk_orders_live(mock: respx.MockRouter) -> None:
    route(mock, "credentials_post_usr_authenticate")
    route(mock, "private_post_odr_orders_bulk")
    route(mock, "private_delete_odr_orders_bulk")
    assert (
        load("bulk_orders").main(
            ["--top", "90000", "--step", "100", "--count", "2", "--amount", "10", "--live"]
        )
        == 0
    )
    assert writes(mock) == ["POST /api/v1/odr/orders/bulk/", "DELETE /api/v1/odr/orders/bulk/"]


def test_bulk_ladder_prices() -> None:
    ladder = load("bulk_orders").ladder
    from decimal import Decimal as D

    assert [o["price"] for o in ladder("A/B", "buy", D(100), D(1), 3, "1")] == [
        D(100),
        D(99),
        D(98),
    ]
    assert [o["price"] for o in ladder("A/B", "sell", D(100), D(1), 2, "1")] == [D(100), D(101)]


def test_market_maker_dry_run(mock: respx.MockRouter, capsys: pytest.CaptureFixture[str]) -> None:
    mock_market_data(mock)
    sleeps: list[float] = []
    assert (
        load("market_maker").main(
            ["--symbol", "BTC/IRT", "--size", "0.001", "--iterations", "2"], sleep=sleeps.append
        )
        == 0
    )
    out = capsys.readouterr().out
    assert out.count("DRY-RUN create_orders") == 2
    assert sleeps == [5.0]
    assert writes(mock) == []


def test_market_maker_live_replaces_quotes(mock: respx.MockRouter) -> None:
    mock_market_data(mock)
    route(mock, "private_post_odr_orders_bulk")
    route(mock, "private_delete_odr_orders_bulk")
    assert (
        load("market_maker").main(
            ["--symbol", "BTC/IRT", "--size", "0.001", "--iterations", "2", "--live"],
            sleep=lambda _: None,
        )
        == 0
    )
    assert writes(mock) == [
        "POST /api/v1/odr/orders/bulk/",
        "DELETE /api/v1/odr/orders/bulk/",
        "POST /api/v1/odr/orders/bulk/",
        "DELETE /api/v1/odr/orders/bulk/",
    ]


def test_market_maker_quotes_round_away_from_mid() -> None:
    from decimal import Decimal as D

    bid, ask = load("market_maker").quotes(D("100.5"), D(20), D(1))
    assert (bid, ask) == (D(100), D(101))


def test_withdraw_live_asks_for_both_codes(mock: respx.MockRouter) -> None:
    route(mock, "credentials_post_usr_authenticate")
    route(mock, "private_post_wlt_withdraws")
    verify = route(mock, "private_post_wlt_withdraws_verify_otp_id", id="7003")
    codes = iter(["111111", "222222"])
    argv = [
        "--currency",
        "USDT",
        "--network",
        "TRX",
        "--address",
        "TTest",
        "--amount",
        "1",
        "--live",
    ]
    assert load("withdraw_with_otp").main(argv, ask=lambda _: next(codes)) == 0
    assert verify.call_count == 2


def test_stream_orderbook(mock: respx.MockRouter, capsys: pytest.CaptureFixture[str]) -> None:
    route(mock, "credentials_post_usr_ws_info")
    book = {"event": "market_data", "symbol": "BTC_IRT", "asks": [["2", "1"]], "bids": [["1", "1"]]}
    trades = {
        "event": "matches_update",
        "symbol": "BTC_IRT",
        "matches": [
            {
                "id": "1",
                "price": "1",
                "base_amount": "1",
                "quote_amount": "1",
                "side": "buy",
                "time": 1.0,
            }
        ],
    }

    class Transport:
        def __init__(self, url: str, get_token: Any) -> None:
            pass

        async def connect(self) -> None:
            pass

        async def subscribe(self, channel: str, on_data: Any) -> None:
            asyncio.get_running_loop().call_soon(
                on_data, book if channel.startswith("orderbook") else trades
            )

        async def close(self) -> None:
            pass

    assert load("stream_orderbook").main(["--updates", "1"], ws_transport_factory=Transport) == 0
    out = capsys.readouterr().out
    assert "book  bid=1 ask=2" in out
    assert "trade buy 1 @ 1" in out


def test_market_maker_cancels_its_quotes_when_an_error_escapes(mock: respx.MockRouter) -> None:
    import httpx

    from bitpin_sdk import errors

    mock_market_data(mock)
    route(mock, "private_post_odr_orders_bulk")
    cancel = route(mock, "private_delete_odr_orders_bulk")
    book = mock.route(method="GET", path__startswith="/api/v1/mth/orderbook/")
    book.side_effect = [
        httpx.Response(200, json={"asks": [["2", "1"]], "bids": [["1", "1"]]}),
        *[httpx.ConnectError("down")] * 4,  # the GET is retried 3 times before it fails
    ]
    with pytest.raises(errors.NetworkError):
        load("market_maker").main(
            ["--symbol", "BTC/IRT", "--size", "0.001", "--iterations", "2", "--live"],
            sleep=lambda _: None,
        )
    assert cancel.call_count == 1


def test_market_maker_ids_are_unique_per_run(mock: respx.MockRouter, capsys: pytest.CaptureFixture[str]) -> None:
    mock_market_data(mock)
    module = load("market_maker")
    module.main(["--symbol", "BTC/IRT", "--size", "1", "--iterations", "1"], sleep=lambda _: None)
    first = capsys.readouterr().out
    module.main(["--symbol", "BTC/IRT", "--size", "1", "--iterations", "1"], sleep=lambda _: None)
    second = capsys.readouterr().out

    def ids(text: str) -> set[str]:
        import re

        return set(re.findall(r'"clientOrderId": "([^"]+)"', text))

    assert ids(first)
    assert ids(first).isdisjoint(ids(second))
