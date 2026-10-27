"""WebSocket watch_* methods, driven by a fake Centrifugo transport."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
import respx

from bitpin_sdk import AsyncBitpin, Bitpin, errors
from bitpin_sdk.ws import BitpinWS
from tests.conftest import FakeTime, route
from tests.fixtures import body


class FakeTransport:
    def __init__(self, url: str, get_token: Callable[[], Awaitable[str]] | None) -> None:
        self.url = url
        self.get_token = get_token
        self.connected = 0
        self.closed = False
        self.handlers: dict[str, Callable[[Any], None]] = {}
        self.token: str | None = None

    async def connect(self) -> None:
        self.connected += 1
        if self.get_token is not None:
            self.token = await self.get_token()

    async def subscribe(self, channel: str, on_data: Callable[[Any], None]) -> None:
        self.handlers[channel] = on_data

    async def close(self) -> None:
        self.closed = True

    def push(self, channel: str, data: Any) -> None:
        self.handlers[channel](data)


@pytest.fixture
def transports() -> list[FakeTransport]:
    return []


@pytest.fixture
async def ws(fake_time: FakeTime, mock: respx.MockRouter, transports: list[FakeTransport]) -> Any:
    def factory(url: str, get_token: Any) -> FakeTransport:
        transport = FakeTransport(url, get_token)
        transports.append(transport)
        return transport

    route(mock, "credentials_post_usr_ws_info")
    client = AsyncBitpin(
        {"api_key": "k", "secret_key": "s"}, clock=fake_time, sleep=fake_time.async_sleep
    )
    socket = BitpinWS(client, transport_factory=factory)
    yield socket
    await socket.close()
    await client.close()


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


TICKER = {
    "price": "3145737420",
    "change": "0.0258",
    "min": "3000000000",
    "max": "3200000000",
    "mean": "3100000000",
    "value": "1500000000000",
    "amount": "480.5",
    "time": "1760873857000",
    "symbol": "BTC_IRT",
    "event_time": "2025-10-19T11:38:27.929164Z",
    "event": "currency_price_update",
}


async def test_watch_ticker(ws: BitpinWS, transports: list[FakeTransport]) -> None:
    task = asyncio.ensure_future(ws.watch_ticker("BTC/IRT"))
    await settle()
    transport = transports[0]
    assert transport.url == "wss://centrifugo.bitpin.org/connection/websocket"
    assert set(transport.handlers) == {"market:BTC_IRT"}
    transport.push("market:BTC_IRT", {"event": "candle_update", "symbol": "BTC_IRT", "candles": []})
    transport.push("market:BTC_IRT", TICKER)
    ticker = await asyncio.wait_for(task, 1)
    assert ticker["symbol"] == "BTC/IRT"
    assert ticker["last"] == D("3145737420")
    assert ticker["percentage"] == D("2.58")
    assert ticker["high"] == D("3200000000")
    assert ticker["baseVolume"] == D("480.5")
    assert ticker["quoteVolume"] == D("1500000000000")
    assert ticker["timestamp"] == 1760873857000


async def test_same_channel_is_subscribed_once(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    first = asyncio.ensure_future(ws.watch_ticker("BTC/IRT"))
    second = asyncio.ensure_future(ws.watch_ohlcv("BTC/IRT", "1m"))
    await settle()
    assert len(transports) == 1
    assert transports[0].connected == 1
    assert list(transports[0].handlers) == ["market:BTC_IRT"]
    first.cancel()
    second.cancel()


async def test_watch_ohlcv_filters_resolution(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    data = {
        "event": "candle_update",
        "symbol": "BTC_IRT",
        "event_time": "2025-10-19T11:38:27.929164Z",
        "candles": [
            {
                "open": "1",
                "close": "2",
                "low": "0.5",
                "high": "3",
                "volume": "10",
                "ts": "1760873760.0",
                "resolution": "1m",
            },
            {
                "open": "1",
                "close": "2",
                "low": "0.5",
                "high": "3",
                "volume": "99",
                "ts": "1760873400.0",
                "resolution": "30m",
            },
        ],
    }
    task = asyncio.ensure_future(ws.watch_ohlcv("BTC/IRT", "1m"))
    await settle()
    transports[0].push("market:BTC_IRT", data)
    candles = await asyncio.wait_for(task, 1)
    assert candles == [[1760873760000, D("1"), D("3"), D("0.5"), D("2"), D("10")]]


async def test_watch_ohlcv_rejects_unknown_timeframe(ws: BitpinWS) -> None:
    with pytest.raises(errors.BadRequest):
        await ws.watch_ohlcv("BTC/IRT", "2h")


async def test_watch_order_book(ws: BitpinWS, transports: list[FakeTransport]) -> None:
    data = {
        "asks": [["3160000000", "0.2"], ["3150000000", "0.01"]],
        "bids": [["3130000000", "1"], ["3140000000", "0.05"]],
        "volume_ask": "0.21",
        "volume_bid": "1.05",
        "price": "3145737420",
        "symbol": "BTC_IRT",
        "event_time": "2025-10-19T11:38:27.929164Z",
        "event": "market_data",
    }
    task = asyncio.ensure_future(ws.watch_order_book("BTC_IRT"))
    await settle()
    assert "orderbook:BTC_IRT" in transports[0].handlers
    transports[0].push("orderbook:BTC_IRT", data)
    book = await asyncio.wait_for(task, 1)
    assert book["bids"][0] == [D("3140000000"), D("0.05")]
    assert book["asks"][0] == [D("3150000000"), D("0.01")]
    assert book["timestamp"] == 1760873907929


async def test_watch_trades(ws: BitpinWS, transports: list[FakeTransport]) -> None:
    data = {
        "matches": [
            {
                "id": "1_2",
                "price": "3145737420",
                "base_amount": "0.002",
                "quote_amount": "6291474.84",
                "side": "buy",
                "time": 1760873797.149016,
            }
        ],
        "symbol": "BTC_IRT",
        "event_time": "2025-10-19T11:38:27.929164Z",
        "event": "matches_update",
    }
    task = asyncio.ensure_future(ws.watch_trades("BTC/IRT"))
    await settle()
    transports[0].push("matches:BTC_IRT", data)
    trades = await asyncio.wait_for(task, 1)
    assert [(t["id"], t["side"], t["amount"]) for t in trades] == [("1_2", "buy", D("0.002"))]
    assert trades[0]["timestamp"] == 1760873797149


async def test_watch_orders_uses_private_channel_and_token(
    ws: BitpinWS, transports: list[FakeTransport], mock: respx.MockRouter
) -> None:
    info = route(mock, "credentials_post_usr_ws_info")
    order = {
        **body("private_post_odr_orders"),
        "market": 1,
        "gain_currency_code": "BTC",
        "resource_currency_code": "IRT",
        "fulfilled": "0.00",
        "event": "user_order_update",
        "event_time": "2025-10-19T11:38:27.929164Z",
    }
    other = {**order, "symbol": "USDT_IRT", "id": 1}
    task = asyncio.ensure_future(ws.watch_orders("BTC/IRT"))
    await settle()
    transport = transports[0]
    assert transport.token == body("credentials_post_usr_ws_info")["ws_token"]
    assert "user:order_info#TESTUSR1" in transport.handlers
    transport.push("user:order_info#TESTUSR1", other)
    transport.push("user:order_info#TESTUSR1", order)
    result = await asyncio.wait_for(task, 1)
    assert result["id"] == "535179385"
    assert result["status"] == "open"
    assert info.call_count == 2  # one for user_identifier, one for the connection token


async def test_watch_my_trades(
    ws: BitpinWS, transports: list[FakeTransport], mock: respx.MockRouter
) -> None:
    route(mock, "credentials_post_usr_ws_info")
    fill = {
        **body("private_get_odr_fills")[0],
        "identifier": "mm-ask-1",
        "event": "user_match_update",
        "event_time": "2025-10-19T11:38:27.929164Z",
    }
    task = asyncio.ensure_future(ws.watch_my_trades())
    await settle()
    transports[0].push(
        "user:order_info#TESTUSR1",
        {**body("private_post_odr_orders"), "event": "user_order_update"},
    )
    transports[0].push("user:order_info#TESTUSR1", fill)
    trade = await asyncio.wait_for(task, 1)
    assert trade["id"] == "65375307"
    assert trade["fee"]["currency"] == "IRT"


async def test_public_only_client_connects_without_token(
    fake_time: FakeTime, transports: list[FakeTransport]
) -> None:
    def factory(url: str, get_token: Any) -> FakeTransport:
        transports.append(FakeTransport(url, get_token))
        return transports[-1]

    client = AsyncBitpin(clock=fake_time, sleep=fake_time.async_sleep)
    socket = BitpinWS(client, transport_factory=factory)
    task = asyncio.ensure_future(socket.watch_trades("BTC/IRT"))
    await settle()
    assert transports[0].get_token is None
    with pytest.raises(errors.AuthenticationError):
        await socket.watch_orders()
    task.cancel()
    await socket.close()
    assert transports[0].closed
    await client.close()


async def test_queue_drops_oldest_when_full(
    fake_time: FakeTime, transports: list[FakeTransport]
) -> None:
    def factory(url: str, get_token: Any) -> FakeTransport:
        transports.append(FakeTransport(url, get_token))
        return transports[-1]

    client = AsyncBitpin(clock=fake_time, sleep=fake_time.async_sleep)
    socket = BitpinWS(client, transport_factory=factory, queue_size=2)
    task = asyncio.ensure_future(socket.watch_ticker("BTC/IRT"))
    await settle()
    task.cancel()
    for price in ("1", "2", "3"):
        transports[0].push("market:BTC_IRT", {**TICKER, "price": price})
    assert (await socket.watch_ticker("BTC/IRT"))["last"] == D("2")
    assert (await socket.watch_ticker("BTC/IRT"))["last"] == D("3")
    await socket.close()
    await client.close()


async def test_client_watch_methods_delegate(
    fake_time: FakeTime, transports: list[FakeTransport]
) -> None:
    def factory(url: str, get_token: Any) -> FakeTransport:
        transports.append(FakeTransport(url, get_token))
        return transports[-1]

    client = AsyncBitpin(clock=fake_time, sleep=fake_time.async_sleep, ws_transport_factory=factory)
    task = asyncio.ensure_future(client.watch_trades("BTC/IRT"))
    await settle()
    assert "matches:BTC_IRT" in transports[0].handlers
    task.cancel()
    await client.close()
    assert transports[0].closed


def test_sync_client_without_keys_refuses_private_channels(fake_time: FakeTime) -> None:
    client = Bitpin(
        clock=fake_time,
        sleep=fake_time.sync_sleep,
        ws_transport_factory=lambda url, token: FakeTransport(url, token),
    )
    with pytest.raises(errors.AuthenticationError, match="private channels"):
        client.watch_orders()
    client.close()


def test_default_transport_is_centrifuge(fake_time: FakeTime) -> None:
    from bitpin_sdk.ws.transport import CentrifugeTransport

    client = AsyncBitpin(clock=fake_time, sleep=fake_time.async_sleep)
    socket = BitpinWS(client)
    assert socket._factory is CentrifugeTransport


async def test_messages_without_event_are_ignored(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    task = asyncio.ensure_future(ws.watch_trades("BTC/IRT"))
    await settle()
    transports[0].push("matches:BTC_IRT", "not a dict")
    transports[0].push("matches:BTC_IRT", {"no": "event"})
    await settle()
    assert not task.done()
    task.cancel()


async def test_second_channel_reuses_connection_and_filters_other_symbols(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    trades = asyncio.ensure_future(ws.watch_trades("BTC/IRT"))
    book = asyncio.ensure_future(ws.watch_order_book("USDT/IRT"))
    await settle()
    assert len(transports) == 1
    assert set(transports[0].handlers) == {"matches:BTC_IRT", "orderbook:USDT_IRT"}
    trades.cancel()
    book.cancel()


async def test_watch_ohlcv_waits_for_matching_resolution(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    task = asyncio.ensure_future(ws.watch_ohlcv("BTC/IRT", "1h"))
    await settle()
    candle = {
        "open": "1",
        "close": "1",
        "low": "1",
        "high": "1",
        "volume": "1",
        "ts": "1760871600.0",
    }
    transports[0].push(
        "market:BTC_IRT",
        {
            "event": "candle_update",
            "symbol": "BTC_IRT",
            "candles": [{**candle, "resolution": "1m"}],
        },
    )
    await settle()
    assert not task.done()
    transports[0].push(
        "market:BTC_IRT",
        {
            "event": "candle_update",
            "symbol": "BTC_IRT",
            "candles": [{**candle, "resolution": "1h"}],
        },
    )
    assert len(await asyncio.wait_for(task, 1)) == 1


async def test_watch_my_trades_filters_symbol(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    fill = {**body("private_get_odr_fills")[0], "event": "user_match_update"}
    task = asyncio.ensure_future(ws.watch_my_trades("BTC/IRT"))
    await settle()
    transports[0].push("user:order_info#TESTUSR1", {**fill, "symbol": "USDT_IRT", "id": 1})
    transports[0].push("user:order_info#TESTUSR1", fill)
    assert (await asyncio.wait_for(task, 1))["id"] == "65375307"


async def test_close_without_connection_is_a_no_op(fake_time: FakeTime) -> None:
    client = AsyncBitpin(clock=fake_time, sleep=fake_time.async_sleep)
    await BitpinWS(client).close()
    await client.close()


async def test_centrifuge_transport_builds_a_client() -> None:
    from bitpin_sdk.ws.transport import CentrifugeTransport

    async def token() -> str:
        return "t"

    transport = CentrifugeTransport("wss://example.invalid/connection/websocket", token)
    assert transport._client is not None


async def test_watchers_for_different_symbols_each_get_their_updates(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    order = {**body("private_post_odr_orders"), "event": "user_order_update"}
    btc = asyncio.ensure_future(ws.watch_orders("BTC/IRT"))
    usdt = asyncio.ensure_future(ws.watch_orders("USDT/IRT"))
    await settle()
    transports[0].push("user:order_info#TESTUSR1", {**order, "symbol": "USDT_IRT", "id": 2})
    transports[0].push("user:order_info#TESTUSR1", {**order, "symbol": "BTC_IRT", "id": 1})
    assert (await asyncio.wait_for(btc, 1))["id"] == "1"
    assert (await asyncio.wait_for(usdt, 1))["id"] == "2"


async def test_two_timeframes_both_see_every_candle_update(
    ws: BitpinWS, transports: list[FakeTransport]
) -> None:
    candle = {
        "open": "1",
        "close": "1",
        "low": "1",
        "high": "1",
        "volume": "1",
        "ts": "1760871600.0",
    }
    one = asyncio.ensure_future(ws.watch_ohlcv("BTC/IRT", "1m"))
    five = asyncio.ensure_future(ws.watch_ohlcv("BTC/IRT", "5m"))
    await settle()
    transports[0].push(
        "market:BTC_IRT",
        {
            "event": "candle_update",
            "symbol": "BTC_IRT",
            "candles": [{**candle, "resolution": "1m"}, {**candle, "resolution": "5m"}],
        },
    )
    assert len(await asyncio.wait_for(one, 1)) == 1
    assert len(await asyncio.wait_for(five, 1)) == 1


async def test_events_nobody_watches_are_not_queued(
    ws: BitpinWS, transports: list[FakeTransport], caplog: pytest.LogCaptureFixture
) -> None:
    task = asyncio.ensure_future(ws.watch_ticker("BTC/IRT"))
    await settle()
    for _ in range(1500):
        transports[0].push(
            "market:BTC_IRT", {"event": "candle_update", "symbol": "BTC_IRT", "candles": []}
        )
    assert "dropped" not in caplog.text
    task.cancel()


async def test_concurrent_private_watchers_share_one_identifier_lookup(
    ws: BitpinWS, transports: list[FakeTransport], mock: respx.MockRouter
) -> None:
    async def slow_ws_info(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)  # a real network call yields to the event loop
        return httpx.Response(200, json=body("credentials_post_usr_ws_info"))

    info = mock.route(method="POST", path="/api/v1/usr/ws-info/").mock(side_effect=slow_ws_info)
    tasks = [asyncio.ensure_future(ws.watch_orders(s)) for s in ("BTC/IRT", "USDT/IRT", None)]
    await settle()
    assert info.call_count == 2  # one for the identifier, one for the connection token
    for task in tasks:
        task.cancel()


async def test_a_failed_identifier_lookup_can_be_retried(
    fake_time: FakeTime, mock: respx.MockRouter
) -> None:
    route(mock, "credentials_post_usr_authenticate")
    route(mock, "credentials_post_usr_ws_info", status=503, json_body=None)
    client = AsyncBitpin(
        {"api_key": "k", "secret_key": "s", "max_retries": 0},
        clock=fake_time,
        sleep=fake_time.async_sleep,
    )
    socket = BitpinWS(client, transport_factory=lambda url, token: FakeTransport(url, token))
    with pytest.raises(errors.ExchangeNotAvailable):
        await socket.watch_orders()
    route(mock, "credentials_post_usr_ws_info")
    assert await socket._user_channel() == "user:order_info#TESTUSR1"
    await client.close()
