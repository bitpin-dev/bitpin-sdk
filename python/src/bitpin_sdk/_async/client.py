"""``AsyncBitpin``: the Bitpin exchange client.

Unified methods use ccxt names and return ccxt structures. Every endpoint in the spec is
also available as an implicit method named after its id, e.g.
``await client.public_get_mkt_tickers()``.

``_sync/client.py`` is generated from this file by ``scripts/gen_sync.py``. Edit this file
only, then regenerate.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, ClassVar

import httpx

from bitpin_sdk import __version__, errors
from bitpin_sdk._async._compat import Lock, default_sleep
from bitpin_sdk._core import parse
from bitpin_sdk._core.auth import TokenState
from bitpin_sdk._core.errors import map_error, not_supported
from bitpin_sdk._core.ratelimit import SlidingWindowLimiter
from bitpin_sdk._core.request import Request, build_request
from bitpin_sdk._core.symbols import to_market_id, to_symbol
from bitpin_sdk._generated.spec import CONSTANTS, ENDPOINTS, HAS, URLS
from bitpin_sdk.config import Config
from bitpin_sdk.token_store import MemoryTokenStore, TokenStore, key_id
from bitpin_sdk.types import (
    OHLCV,
    Currency,
    Market,
    Network,
    OrderBook,
    Ticker,
    Trade,
    TradingFee,
)

logger = logging.getLogger("bitpin_sdk")

#: ccxt timeframe → seconds. Bitpin's candle resolutions use the same names.
TIMEFRAMES: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "3h": 10800,
    "4h": 14400,
    "6h": 21600,
    "1d": 86400,
    "1w": 604800,
    "1M": 2592000,
}
_MAX_RATE_LIMIT_WAIT = 5.0
_DEFAULT_OHLCV_LIMIT = 500


class AsyncBitpin:
    """Async client for the Bitpin exchange.

    ``config`` is a :class:`Config`, a ccxt-style dict (``{"apiKey": ..., "secret": ...}``)
    or a dict of ``Config`` fields. ``clock`` and ``sleep`` exist for tests.
    """

    id = "bitpin"
    name = "Bitpin"
    has: ClassVar[dict[str, bool]] = HAS
    timeframes: ClassVar[dict[str, str]] = {tf: tf for tf in TIMEFRAMES}

    def __init__(
        self,
        config: Config | Mapping[str, Any] | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Any] = default_sleep,
    ) -> None:
        self.config = Config.coerce(config)
        self._clock = clock
        self._sleep = sleep
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=self.config.timeout)
        self._limiter = SlidingWindowLimiter(self.config.all_rate_limits(), clock)
        self._tokens = TokenState(clock)
        self._store: TokenStore = self.config.token_store or MemoryTokenStore()
        self._store_loaded = False
        self._auth_lock = Lock()
        self.markets: dict[str, Market] = {}
        self.markets_by_id: dict[str, Market] = {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(config={self.config!r})"

    async def __aenter__(self) -> AsyncBitpin:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP connection pool (only if the client created it)."""
        if self._owns_http:
            await self._http.aclose()

    def describe(self) -> dict[str, Any]:
        """ccxt-style description: urls, capabilities, timeframes and effective rate limits."""
        return {
            "id": self.id,
            "name": self.name,
            "urls": {"api": self.config.rest_url, "ws": self.config.ws_url, "doc": URLS["docs"]},
            "has": dict(self.has),
            "timeframes": dict(self.timeframes),
            "rateLimits": {
                name: f"{rule.limit}/{rule.period}"
                for name, rule in self.config.all_rate_limits().items()
            },
        }

    # --- transport -------------------------------------------------------------

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name in ENDPOINTS:

            def implicit(params: Mapping[str, Any] | None = None, *, body: Any = None) -> Any:
                return self._implicit(name, params, body)

            implicit.__name__ = name
            return implicit
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    async def _implicit(self, endpoint_id: str, params: Mapping[str, Any] | None, body: Any) -> Any:
        path = ENDPOINTS[endpoint_id].path
        values = dict(params or {})
        path_params = {k: values.pop(k) for k in list(values) if "{" + k + "}" in path}
        if ENDPOINTS[endpoint_id].method == "GET":
            return await self.request(endpoint_id, path_params, params=values)
        return await self.request(endpoint_id, path_params, body=values if body is None else body)

    async def request(
        self,
        endpoint_id: str,
        path_params: Mapping[str, Any] | None = None,
        *,
        params: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        """Call one endpoint: rate limit, authenticate, send, map errors, retry if safe."""
        req = build_request(self.config, endpoint_id, path_params, params, body)
        reauthenticated = False
        attempt = 0
        while True:
            token = await self._access_token() if req.auth == "private" else None
            try:
                return await self._send(req, token)
            except errors.AuthenticationError:
                if req.auth != "private" or reauthenticated:
                    raise
                reauthenticated = True
                self._tokens.expire_access()
            except errors.NetworkError as exc:
                wait = self._retry_delay(req, exc, attempt)
                if wait is None:
                    raise
                attempt += 1
                await self._sleep(wait)

    def _retry_delay(self, req: Request, exc: errors.NetworkError, attempt: int) -> float | None:
        if not req.idempotent or attempt >= self.config.max_retries:
            return None
        if isinstance(exc, errors.RateLimitExceeded):
            if exc.retry_after is None or exc.retry_after > _MAX_RATE_LIMIT_WAIT:
                return None
            return float(exc.retry_after)
        return 0.5 * float(1 << attempt)

    async def _send(self, req: Request, token: str | None) -> Any:
        if self.config.enable_rate_limit:
            wait = self._limiter.delay(req.buckets)
            if wait > 0:
                await self._sleep(wait)
            self._limiter.record(req.buckets)
        headers = {
            "Accept": "application/json",
            "User-Agent": self.config.user_agent or f"bitpin-sdk-python/{__version__}",
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = await self._http.request(
                req.method,
                req.url,
                params=req.params,
                json=req.json,
                headers=headers,
                timeout=self.config.timeout,
            )
        except httpx.TimeoutException as exc:
            raise errors.RequestTimeout(
                f"{req.endpoint_id}: request timed out", endpoint_id=req.endpoint_id
            ) from exc
        except httpx.TransportError as exc:
            raise errors.NetworkError(
                f"{req.endpoint_id}: {type(exc).__name__}", endpoint_id=req.endpoint_id
            ) from exc
        logger.debug("%s %s -> %s", req.method, req.url, response.status_code)
        body = _decode(response)
        if response.status_code >= 400:
            raise map_error(
                req.endpoint_id,
                response.status_code,
                None if body is _INVALID else body,
                retry_after_header=response.headers.get("retry-after"),
            )
        if response.status_code != 204 and response.content and body is _INVALID:
            raise errors.ExchangeError(
                f"{req.endpoint_id}: invalid JSON in response",
                status=response.status_code,
                body=response.text,
                endpoint_id=req.endpoint_id,
            )
        return None if body is _INVALID else body

    # --- authentication --------------------------------------------------------

    def _credentials(self) -> dict[str, str]:
        if not self.config.has_credentials:
            raise errors.AuthenticationError(
                "api_key and secret_key are required for private endpoints"
            )
        return {"api_key": str(self.config.api_key), "secret_key": str(self.config.secret_key)}

    async def _access_token(self) -> str:
        async with self._auth_lock:
            credentials = self._credentials()
            store_key = key_id(credentials["api_key"])
            if not self._store_loaded:
                self._store_loaded = True
                stored = self._store.load(store_key)
                if stored is not None:
                    self._tokens.load(stored)
            action = self._tokens.action()
            if action == "refresh" and self._tokens.tokens is not None:
                refresh = build_request(
                    self.config,
                    "credentials_post_usr_refresh_token",
                    body={"refresh": self._tokens.tokens.refresh},
                )
                try:
                    self._store.save(
                        store_key, self._tokens.set_access(await self._send(refresh, None))
                    )
                    action = "ok"
                except (errors.AuthenticationError, errors.BadRequest):
                    action = "authenticate"
            if action == "authenticate":
                login = build_request(
                    self.config, "credentials_post_usr_authenticate", body=credentials
                )
                self._store.save(store_key, self._tokens.set_tokens(await self._send(login, None)))
            return str(self._tokens.access_token)

    # --- markets ---------------------------------------------------------------

    async def fetch_markets(self) -> list[Market]:
        rows = await self.request("public_get_mkt_markets")
        return [parse.parse_market(row) for row in rows]

    async def load_markets(self, reload: bool = False) -> dict[str, Market]:
        """Fetch markets once and cache them in ``markets`` and ``markets_by_id``."""
        if reload or not self.markets:
            markets = await self.fetch_markets()
            self.markets = {m["symbol"]: m for m in markets}
            self.markets_by_id = {m["id"]: m for m in markets}
        return self.markets

    def market(self, symbol: str) -> Market:
        """The cached market for ``BTC/IRT`` or ``BTC_IRT``. Call ``load_markets()`` first."""
        if not self.markets:
            raise errors.BitpinError("markets not loaded; call load_markets() first")
        market = self.markets_by_id.get(to_market_id(symbol))
        if market is None:
            raise errors.BadSymbol(f"unknown market {to_symbol(to_market_id(symbol))}")
        return market

    async def fetch_currencies(self) -> dict[str, Currency]:
        rows = await self.request("public_get_mkt_currencies")
        return {c["code"]: c for c in (parse.parse_currency(row) for row in rows)}

    async def fetch_networks(self, params: Mapping[str, Any] | None = None) -> list[Network]:
        """All networks. ``params``: ``code``, ``can_deposit``, ``can_withdraw``."""
        rows = await self.request("public_get_mkt_networks", params=params)
        return [parse.parse_network(row) for row in rows]

    async def fetch_market_suspensions(self) -> dict[str, bool]:
        """``{symbol: suspended}`` for your account. Limited to 2 requests per minute."""
        rows = await self.request("private_get_mkt_markets_suspensions")
        return {to_symbol(str(row["code"])): bool(row["suspended"]) for row in rows}

    # --- tickers, order book, trades, candles ----------------------------------

    async def fetch_tickers(self, symbols: Sequence[str] | None = None) -> dict[str, Ticker]:
        rows = await self.request("public_get_mkt_tickers")
        tickers = {t["symbol"]: t for t in (parse.parse_ticker(row) for row in rows)}
        if symbols is None:
            return tickers
        wanted = {to_symbol(to_market_id(s)) for s in symbols}
        return {s: t for s, t in tickers.items() if s in wanted}

    async def fetch_ticker(self, symbol: str) -> Ticker:
        unified = to_symbol(to_market_id(symbol))
        tickers = await self.fetch_tickers([unified])
        if unified not in tickers:
            raise errors.BadSymbol(f"no ticker for {unified}")
        return tickers[unified]

    async def fetch_order_book(self, symbol: str, limit: int | None = None) -> OrderBook:
        """Top of the book (default 20 levels, at most 50)."""
        if limit is not None and limit > CONSTANTS["orderbook_max_limit"]:
            raise errors.BadRequest(
                f"order book limit is at most {CONSTANTS['orderbook_max_limit']}"
            )
        market_id = to_market_id(symbol)
        raw = await self.request(
            "public_get_mth_orderbook_symbol", {"symbol": market_id}, params={"limit": limit}
        )
        return parse.parse_order_book(raw, to_symbol(market_id))

    async def fetch_trades(
        self, symbol: str, since: int | None = None, limit: int | None = None
    ) -> list[Trade]:
        """Recent public trades, oldest first. ``since`` (ms) and ``limit`` filter client-side."""
        market_id = to_market_id(symbol)
        rows = await self.request("public_get_mth_matches_symbol", {"symbol": market_id})
        trades = [parse.parse_trade(row, to_symbol(market_id)) for row in rows]
        trades.sort(key=lambda t: t["timestamp"] or 0)
        return _filter_since_limit(trades, since, limit)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "30m",
        since: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[OHLCV]:
        """Candles ``[ms, open, high, low, close, volume]``, oldest first.

        Without ``since``, returns the latest ``limit`` candles (default 500).
        """
        if timeframe not in TIMEFRAMES:
            raise errors.BadRequest(
                f"timeframe {timeframe!r} is not supported; use one of {', '.join(TIMEFRAMES)}"
            )
        step = TIMEFRAMES[timeframe]
        count = limit or _DEFAULT_OHLCV_LIMIT
        if count > CONSTANTS["candles_max_per_request"]:
            raise errors.BadRequest(
                f"at most {CONSTANTS['candles_max_per_request']} candles per request"
            )
        if since is None:
            end = int(self._clock())
            start = end - count * step
        else:
            start = since // 1000
            end = start + count * step
        query = {
            "symbol": to_market_id(symbol),
            "res": timeframe,
            "from": start,
            "to": end,
            **(params or {}),
        }
        rows = await self.request("public_get_mkt_candles", params=query)
        candles = [parse.parse_ohlcv(row) for row in rows]
        return candles[-count:] if since is None else candles[:count]

    # --- fees --------------------------------------------------------------------

    async def fetch_trading_fees(self) -> dict[str, TradingFee]:
        """Your maker/taker fees per market, as ratios (0.003 = 0.3 %)."""
        rows = await self.request("private_get_mkt_commissions")
        return {f["symbol"]: f for f in (parse.parse_trading_fee(row) for row in rows)}

    async def fetch_trading_fee(self, symbol: str) -> TradingFee:
        unified = to_symbol(to_market_id(symbol))
        fees = await self.fetch_trading_fees()
        if unified not in fees:
            raise errors.BadSymbol(f"no trading fee for {unified}")
        return fees[unified]


_INVALID: Any = object()


def _decode(response: httpx.Response) -> Any:
    if not response.content:
        return _INVALID
    try:
        return response.json()
    except ValueError:
        return response.text if response.status_code >= 400 else _INVALID


def _filter_since_limit(items: Iterable[Any], since: int | None, limit: int | None) -> list[Any]:
    result = [i for i in items if since is None or (i["timestamp"] or 0) >= since]
    return result[-limit:] if limit else result


__all__ = ["TIMEFRAMES", "AsyncBitpin", "not_supported"]
