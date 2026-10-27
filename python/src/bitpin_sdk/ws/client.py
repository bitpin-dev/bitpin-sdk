"""``BitpinWS``: ccxt.pro-style ``watch_*`` methods over Centrifugo.

Each ``watch_*`` call subscribes once (the first time) and returns the next update. Updates
that arrive between calls are queued (``queue_size`` per channel and event, oldest dropped
first), so a loop like ``while True: await ws.watch_trades(s)`` doesn't miss any.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bitpin_sdk import errors
from bitpin_sdk._async.client import TIMEFRAMES
from bitpin_sdk._core.symbols import to_market_id
from bitpin_sdk._generated.spec import WS_CHANNELS
from bitpin_sdk.types import OHLCV, Order, OrderBook, Ticker, Trade
from bitpin_sdk.ws import parse
from bitpin_sdk.ws.transport import CentrifugeTransport, GetToken, Transport, TransportFactory

if TYPE_CHECKING:
    from bitpin_sdk._async.client import AsyncBitpin

logger = logging.getLogger("bitpin_sdk.ws")


class BitpinWS:
    def __init__(
        self,
        client: AsyncBitpin,
        *,
        transport_factory: TransportFactory | None = None,
        queue_size: int = 1000,
    ) -> None:
        self._client = client
        self._factory: TransportFactory = transport_factory or CentrifugeTransport
        self._queue_size = queue_size
        self._transport: Transport | None = None
        self._lock = asyncio.Lock()
        self._channels: set[str] = set()
        self._queues: dict[tuple[str, str], asyncio.Queue[Any]] = {}
        self._user_identifier: str | None = None

    async def close(self) -> None:
        if self._transport is not None:
            await self._transport.close()
            self._transport = None
            self._channels.clear()

    # --- connection --------------------------------------------------------------

    async def _ws_info(self) -> dict[str, Any]:
        info: dict[str, Any] = await self._client.request(
            "credentials_post_usr_ws_info", body=self._client._credentials()
        )
        return info

    async def _token(self) -> str:
        return str((await self._ws_info())["ws_token"])

    async def _connection(self) -> Transport:
        if self._transport is None:
            get_token: GetToken | None = (
                self._token if self._client.config.has_credentials else None
            )
            self._transport = self._factory(self._client.config.ws_url, get_token)
            await self._transport.connect()
        return self._transport

    def _queue(self, channel: str, event: str) -> asyncio.Queue[Any]:
        key = (channel, event)
        if key not in self._queues:
            self._queues[key] = asyncio.Queue(maxsize=self._queue_size)
        return self._queues[key]

    def _on_data(self, channel: str) -> Callable[[Any], None]:
        def handle(data: Any) -> None:
            event = data.get("event") if isinstance(data, dict) else None
            if event is None:
                return
            queue = self._queue(channel, str(event))
            if queue.full():
                queue.get_nowait()
                logger.warning("dropped an old %s update on %s; read faster", event, channel)
            queue.put_nowait(data)

        return handle

    async def _next(self, channel: str, event: str) -> Any:
        queue = self._queue(channel, event)
        async with self._lock:
            if channel not in self._channels:
                transport = await self._connection()
                await transport.subscribe(channel, self._on_data(channel))
                self._channels.add(channel)
        return await queue.get()

    async def _user_channel(self) -> str:
        if not self._client.config.has_credentials:
            raise errors.AuthenticationError(
                "api_key and secret_key are required for private channels"
            )
        if self._user_identifier is None:
            self._user_identifier = str((await self._ws_info())["user_identifier"])
        return WS_CHANNELS["user_orders"].format(user_identifier=self._user_identifier)

    # --- public channels -------------------------------------------------------------

    async def watch_ticker(self, symbol: str) -> Ticker:
        channel = WS_CHANNELS["market"].format(symbol=to_market_id(symbol))
        return parse.parse_ticker(await self._next(channel, "currency_price_update"))

    async def watch_ohlcv(self, symbol: str, timeframe: str = "1m") -> list[OHLCV]:
        """The latest candles of ``timeframe`` (Bitpin pushes every 10 s and on trades)."""
        if timeframe not in TIMEFRAMES:
            raise errors.BadRequest(f"timeframe {timeframe!r} is not supported")
        channel = WS_CHANNELS["market"].format(symbol=to_market_id(symbol))
        while True:
            candles = parse.parse_ohlcv(await self._next(channel, "candle_update"), timeframe)
            if candles:
                return candles

    async def watch_order_book(self, symbol: str) -> OrderBook:
        channel = WS_CHANNELS["orderbook"].format(symbol=to_market_id(symbol))
        return parse.parse_order_book(await self._next(channel, "market_data"))

    async def watch_trades(self, symbol: str) -> list[Trade]:
        channel = WS_CHANNELS["matches"].format(symbol=to_market_id(symbol))
        return parse.parse_trades(await self._next(channel, "matches_update"))

    # --- private channel ----------------------------------------------------------------

    async def watch_orders(self, symbol: str | None = None) -> Order:
        """The next update of one of your orders (created, filled, cancelled)."""
        channel = await self._user_channel()
        wanted = to_market_id(symbol) if symbol else None
        while True:
            data = await self._next(channel, "user_order_update")
            if wanted is None or data.get("symbol") == wanted:
                return parse.parse_order(data)

    async def watch_my_trades(self, symbol: str | None = None) -> Trade:
        """The next fill of one of your orders."""
        channel = await self._user_channel()
        wanted = to_market_id(symbol) if symbol else None
        while True:
            data = await self._next(channel, "user_match_update")
            if wanted is None or data.get("symbol") == wanted:
                return parse.parse_my_trade(data)
