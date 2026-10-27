"""WebSocket for the sync ``Bitpin``: the async client runs on a background thread.

Each ``watch_*`` call blocks until the next update (or ``timeout``). One thread and one
Centrifugo connection serve every watch of the client; ``close()`` stops them.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

from bitpin_sdk.types import OHLCV, Order, OrderBook, Ticker, Trade

T = TypeVar("T")


class SyncWS:
    def __init__(self, client: Any, transport_factory: Any) -> None:
        self._config = client.config
        self._factory = transport_factory
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._async: Any = None

    def _run(self, make: Any) -> Any:
        with self._lock:
            if self._loop is None:
                from bitpin_sdk._async.client import AsyncBitpin  # avoids an import cycle

                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._loop.run_forever, name="bitpin-ws", daemon=True
                )
                self._thread.start()
                self._async = AsyncBitpin(self._config, ws_transport_factory=self._factory)
            loop = self._loop
        coroutine: Coroutine[Any, Any, Any] = make(self._async)
        return asyncio.run_coroutine_threadsafe(coroutine, loop).result()

    def close(self) -> None:
        with self._lock:
            loop, thread, client = self._loop, self._thread, self._async
            self._loop = self._thread = self._async = None
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(client.close(), loop).result()
        finally:
            loop.call_soon_threadsafe(loop.stop)
            if thread is not None:
                thread.join()
            loop.close()

    def watch_ticker(self, symbol: str, timeout: float | None = None) -> Ticker:
        result: Ticker = self._run(lambda c: c.watch_ticker(symbol, timeout))
        return result

    def watch_ohlcv(
        self, symbol: str, timeframe: str = "1m", timeout: float | None = None
    ) -> list[OHLCV]:
        result: list[OHLCV] = self._run(lambda c: c.watch_ohlcv(symbol, timeframe, timeout))
        return result

    def watch_order_book(self, symbol: str, timeout: float | None = None) -> OrderBook:
        result: OrderBook = self._run(lambda c: c.watch_order_book(symbol, timeout))
        return result

    def watch_trades(self, symbol: str, timeout: float | None = None) -> list[Trade]:
        result: list[Trade] = self._run(lambda c: c.watch_trades(symbol, timeout))
        return result

    def watch_orders(self, symbol: str | None = None, timeout: float | None = None) -> Order:
        result: Order = self._run(lambda c: c.watch_orders(symbol, timeout))
        return result

    def watch_my_trades(self, symbol: str | None = None, timeout: float | None = None) -> Trade:
        result: Trade = self._run(lambda c: c.watch_my_trades(symbol, timeout))
        return result
