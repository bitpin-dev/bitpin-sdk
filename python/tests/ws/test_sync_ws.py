"""The sync client's watch_* methods run the async WebSocket client on a background thread."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
import respx

from bitpin_sdk import Bitpin, errors
from tests.conftest import FakeTime, route
from tests.fixtures import body
from tests.ws.test_ws import TICKER, FakeTransport


def wait_for(predicate: Any, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("timed out")
        time.sleep(0.005)


@pytest.fixture
def sync_env(fake_time: FakeTime, mock: respx.MockRouter) -> Any:
    transports: list[FakeTransport] = []

    def factory(url: str, get_token: Any) -> FakeTransport:
        transports.append(FakeTransport(url, get_token))
        return transports[-1]

    route(mock, "credentials_post_usr_ws_info")
    client = Bitpin(
        {"api_key": "k", "secret_key": "s"},
        clock=fake_time,
        sleep=fake_time.sync_sleep,
        ws_transport_factory=factory,
    )
    yield client, transports
    client.close()


def push_soon(client: Bitpin, transports: list[FakeTransport], channel: str, data: Any) -> None:
    """Deliver a message on the WebSocket thread, as Centrifugo's callbacks are."""

    def run() -> None:
        wait_for(lambda: transports and channel in transports[0].handlers)
        client._ws._loop.call_soon_threadsafe(transports[0].push, channel, data)

    threading.Thread(target=run, daemon=True).start()


def test_sync_watch_ticker_blocks_until_the_next_update(sync_env: Any) -> None:
    client, transports = sync_env
    push_soon(client, transports, "market:BTC_IRT", TICKER)
    ticker = client.watch_ticker("BTC/IRT")
    assert ticker["symbol"] == "BTC/IRT"
    assert str(ticker["percentage"]) == "2.5800"
    assert transports[0].token == body("credentials_post_usr_ws_info")["ws_token"]


def test_sync_watch_orders_and_trades(sync_env: Any) -> None:
    client, transports = sync_env
    order = {**body("private_post_odr_orders"), "event": "user_order_update"}
    push_soon(client, transports, "user:order_info#TESTUSR1", order)
    assert client.watch_orders("BTC/IRT")["id"] == "535179385"
    push_soon(
        client,
        transports,
        "matches:BTC_IRT",
        {
            "event": "matches_update",
            "symbol": "BTC_IRT",
            "matches": [
                {
                    "id": "1_2",
                    "price": "1",
                    "base_amount": "1",
                    "quote_amount": "1",
                    "side": "buy",
                    "time": 1.0,
                }
            ],
        },
    )
    assert client.watch_trades("BTC/IRT")[0]["id"] == "1_2"


def test_sync_watch_errors_reach_the_caller(sync_env: Any) -> None:
    client, _ = sync_env
    with pytest.raises(errors.BadRequest):
        client.watch_ohlcv("BTC/IRT", "2h")


def test_sync_watch_timeout(sync_env: Any) -> None:
    client, _ = sync_env
    with pytest.raises(errors.RequestTimeout, match="no update"):
        client.watch_order_book("BTC/IRT", timeout=0.05)


def test_close_stops_the_background_thread(fake_time: FakeTime, mock: respx.MockRouter) -> None:
    route(mock, "credentials_post_usr_ws_info")
    transports: list[FakeTransport] = []
    client = Bitpin(
        {"api_key": "k", "secret_key": "s"},
        clock=fake_time,
        sleep=fake_time.sync_sleep,
        ws_transport_factory=lambda url, tok: (
            transports.append(FakeTransport(url, tok)) or transports[-1]
        ),
    )
    push_soon(client, transports, "market:BTC_IRT", TICKER)
    client.watch_ticker("BTC/IRT")
    thread = client._ws._thread
    assert thread.is_alive()
    client.close()
    thread.join(1)
    assert not thread.is_alive()
    assert transports[0].closed
    client.close()
