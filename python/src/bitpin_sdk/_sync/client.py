# Generated from _async/client.py by scripts/gen_sync.py. Do not edit.
"""``Bitpin``: the Bitpin exchange client.

Unified methods use ccxt names and return ccxt structures. Every endpoint in the spec is
also available as an implicit method named after its id, e.g.
``client.public_get_mkt_tickers()``.

Generated from ``_async/client.py``; edit that file instead.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, ClassVar

import httpx

from bitpin_sdk import __version__, errors
from bitpin_sdk._sync._compat import Lock, default_sleep, websocket
from bitpin_sdk._core import parse
from bitpin_sdk._core.auth import TokenState
from bitpin_sdk._core.errors import map_error, not_supported
from bitpin_sdk._core.numbers import Number, to_decimal
from bitpin_sdk._core.ratelimit import SlidingWindowLimiter
from bitpin_sdk._core.request import Request, build_request
from bitpin_sdk._core.symbols import to_market_id, to_symbol
from bitpin_sdk._generated.spec import CONSTANTS, ENDPOINTS, HAS, URLS
from bitpin_sdk.config import Config
from bitpin_sdk.token_store import MemoryTokenStore, TokenStore, key_id
from bitpin_sdk.types import (
    OHLCV,
    Balances,
    BankAccount,
    CancelResult,
    Currency,
    DepositAddress,
    Market,
    Network,
    Order,
    OrderBook,
    Ticker,
    Trade,
    TradingFee,
    Transaction,
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


class Bitpin:
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
        http_client: httpx.Client | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Any] = default_sleep,
        ws_transport_factory: Any = None,
    ) -> None:
        self.config = Config.coerce(config)
        self._clock = clock
        self._sleep = sleep
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=self.config.timeout)
        self._limiter = SlidingWindowLimiter(self.config.all_rate_limits(), clock)
        self._tokens = TokenState(clock)
        self._store: TokenStore = self.config.token_store or MemoryTokenStore()
        self._store_loaded = False
        self._store_key: str | None = None
        self._auth_lock = Lock()
        self._ws_factory = ws_transport_factory
        self._ws: Any = None
        self.markets: dict[str, Market] = {}
        self.markets_by_id: dict[str, Market] = {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(config={self.config!r})"

    def __enter__(self) -> Bitpin:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the WebSocket and the HTTP connection pool (if the client created it)."""
        ws, self._ws = self._ws, None
        try:
            if ws is not None:
                ws.close()
        finally:
            if self._owns_http:
                self._http.close()

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

    def _implicit(self, endpoint_id: str, params: Mapping[str, Any] | None, body: Any) -> Any:
        path = ENDPOINTS[endpoint_id].path
        values = dict(params or {})
        path_params = {k: values.pop(k) for k in list(values) if "{" + k + "}" in path}
        if ENDPOINTS[endpoint_id].method == "GET":
            return self.request(endpoint_id, path_params, params=values)
        return self.request(endpoint_id, path_params, body=values if body is None else body)

    def request(
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
            token = self._access_token() if req.auth == "private" else None
            try:
                return self._send(req, token)
            except errors.AuthenticationError:
                if req.auth != "private" or reauthenticated:
                    raise
                reauthenticated = True
                self._tokens.expire_access(token)
            except errors.NetworkError as exc:
                wait = self._retry_delay(req, exc, attempt)
                if wait is None:
                    raise
                attempt += 1
                self._sleep(wait)

    def _retry_delay(self, req: Request, exc: errors.NetworkError, attempt: int) -> float | None:
        if not req.idempotent or attempt >= self.config.max_retries:
            return None
        if isinstance(exc, errors.RateLimitExceeded):
            if exc.retry_after is None or exc.retry_after > _MAX_RATE_LIMIT_WAIT:
                return None
            return float(exc.retry_after)
        return 0.5 * float(1 << attempt)

    def _send(self, req: Request, token: str | None) -> Any:
        if self.config.enable_rate_limit:
            wait = self._limiter.reserve(req.buckets)
            if wait > 0:
                self._sleep(wait)
        headers = {
            "Accept": "application/json",
            "User-Agent": self.config.user_agent or f"bitpin-sdk-python/{__version__}",
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self._http.request(
                req.method,
                req.url,
                params=req.params,
                json=req.json,
                headers=headers,
                timeout=self.config.timeout,
            )
        except httpx.TransportError as exc:
            error_class = (
                errors.RequestTimeout
                if isinstance(exc, httpx.TimeoutException)
                else errors.NetworkError
            )
            reason = (
                "request timed out" if error_class is errors.RequestTimeout else type(exc).__name__
            )
            error = error_class(f"{req.endpoint_id}: {reason}", endpoint_id=req.endpoint_id)
            if req.auth == "credentials":
                # The httpx exception holds the request, whose body has the credentials.
                raise error from None
            raise error from exc
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

    def _access_token(self) -> str:
        with self._auth_lock:
            credentials = self._credentials()
            if self._store_key is None:  # PBKDF2 is slow on purpose; derive it once
                self._store_key = key_id(credentials["api_key"])
            store_key = self._store_key
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
                        store_key, self._tokens.set_access(self._send(refresh, None))
                    )
                    action = "ok"
                except (errors.AuthenticationError, errors.BadRequest):
                    action = "authenticate"
            if action == "authenticate":
                login = build_request(
                    self.config, "credentials_post_usr_authenticate", body=credentials
                )
                self._store.save(store_key, self._tokens.set_tokens(self._send(login, None)))
            return str(self._tokens.access_token)

    # --- markets ---------------------------------------------------------------

    def fetch_markets(self) -> list[Market]:
        rows = self.request("public_get_mkt_markets")
        return [parse.parse_market(row) for row in rows]

    def load_markets(self, reload: bool = False) -> dict[str, Market]:
        """Fetch markets once and cache them in ``markets`` and ``markets_by_id``."""
        if reload or not self.markets:
            markets = self.fetch_markets()
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

    def fetch_currencies(self) -> dict[str, Currency]:
        rows = self.request("public_get_mkt_currencies")
        return {c["code"]: c for c in (parse.parse_currency(row) for row in rows)}

    def fetch_networks(self, params: Mapping[str, Any] | None = None) -> list[Network]:
        """All networks. ``params``: ``code``, ``can_deposit``, ``can_withdraw``."""
        rows = self.request("public_get_mkt_networks", params=params)
        return [parse.parse_network(row) for row in rows]

    def fetch_market_suspensions(self) -> dict[str, bool]:
        """``{symbol: suspended}`` for your account. Limited to 2 requests per minute."""
        rows = self.request("private_get_mkt_markets_suspensions")
        return {to_symbol(str(row["code"])): bool(row["suspended"]) for row in rows}

    # --- tickers, order book, trades, candles ----------------------------------

    def fetch_tickers(self, symbols: Sequence[str] | None = None) -> dict[str, Ticker]:
        rows = self.request("public_get_mkt_tickers")
        tickers = {t["symbol"]: t for t in (parse.parse_ticker(row) for row in rows)}
        if symbols is None:
            return tickers
        wanted = {to_symbol(to_market_id(s)) for s in symbols}
        return {s: t for s, t in tickers.items() if s in wanted}

    def fetch_ticker(self, symbol: str) -> Ticker:
        unified = to_symbol(to_market_id(symbol))
        tickers = self.fetch_tickers([unified])
        if unified not in tickers:
            raise errors.BadSymbol(f"no ticker for {unified}")
        return tickers[unified]

    def fetch_order_book(self, symbol: str, limit: int | None = None) -> OrderBook:
        """Top of the book (default 20 levels, at most 50)."""
        if limit is not None and limit > CONSTANTS["orderbook_max_limit"]:
            raise errors.BadRequest(
                f"order book limit is at most {CONSTANTS['orderbook_max_limit']}"
            )
        market_id = to_market_id(symbol)
        raw = self.request(
            "public_get_mth_orderbook_symbol", {"symbol": market_id}, params={"limit": limit}
        )
        return parse.parse_order_book(raw, to_symbol(market_id))

    def fetch_trades(
        self, symbol: str, since: int | None = None, limit: int | None = None
    ) -> list[Trade]:
        """Recent public trades, oldest first. ``since`` (ms) and ``limit`` filter client-side."""
        market_id = to_market_id(symbol)
        rows = self.request("public_get_mth_matches_symbol", {"symbol": market_id})
        trades = [parse.parse_trade(row, to_symbol(market_id)) for row in rows]
        trades.sort(key=lambda t: t["timestamp"] or 0)
        return _filter_since_limit(trades, since, limit)

    def fetch_ohlcv(
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
        if limit is not None and limit < 1:
            raise errors.BadRequest("fetch_ohlcv limit must be at least 1")
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
        rows = self.request("public_get_mkt_candles", params=query)
        candles = [parse.parse_ohlcv(row) for row in rows]
        return candles[-count:] if since is None else candles[:count]

    # --- fees --------------------------------------------------------------------

    def fetch_trading_fees(self) -> dict[str, TradingFee]:
        """Your maker/taker fees per market, as ratios (0.003 = 0.3 %)."""
        rows = self.request("private_get_mkt_commissions")
        return {f["symbol"]: f for f in (parse.parse_trading_fee(row) for row in rows)}

    def fetch_trading_fee(self, symbol: str) -> TradingFee:
        unified = to_symbol(to_market_id(symbol))
        fees = self.fetch_trading_fees()
        if unified not in fees:
            raise errors.BadSymbol(f"no trading fee for {unified}")
        return fees[unified]

    # --- orders ------------------------------------------------------------------

    def create_order(
        self,
        symbol: str,
        type: str,
        side: str,
        amount: Number | None = None,
        price: Number | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Order:
        """Place an order. ``type``: ``limit``, ``market``, ``stop_limit`` or ``oco``.

        ``params``: ``clientOrderId``; ``quoteAmount`` (market orders by quote);
        ``stopPrice``/``triggerPrice`` (stop_limit, oco); ``takeProfitPrice`` (oco target).
        """
        body = order_body(symbol, type, side, amount, price, params)
        return parse.parse_order(self.request("private_post_odr_orders", body=body))

    def create_orders(self, orders: Sequence[Mapping[str, Any]]) -> list[Order]:
        """Place up to 10 orders in one atomic request. Each item has the keys of
        ``create_order``: ``symbol``, ``type``, ``side``, ``amount``, ``price``, ``params``."""
        if not orders:
            raise errors.BadRequest("create_orders needs at least one order")
        if len(orders) > CONSTANTS["bulk_orders_max"]:
            raise errors.BadRequest(
                f"create_orders takes at most {CONSTANTS['bulk_orders_max']} orders"
            )
        body = [
            order_body(
                o["symbol"], o["type"], o["side"], o.get("amount"), o.get("price"), o.get("params")
            )
            for o in orders
        ]
        return parse.parse_bulk_orders(
            self.request("private_post_odr_orders_bulk", body=body)
        )

    def fetch_order(self, id: str | int, symbol: str | None = None) -> Order:
        raw = self.request("private_get_odr_orders_id", {"id": id})
        return parse.parse_order(raw)

    def fetch_orders(
        self,
        symbol: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[Order]:
        """Active orders and orders closed in the last 7 days, oldest first.

        ``params``: ``state``, ``side``, ``type`` (lists allowed), ``identifier``,
        ``ids_in``, ``identifiers_in``, ``end`` (ISO time); ``paginate=True`` reads every page.
        """
        query: dict[str, Any] = {
            "symbol": to_market_id(symbol) if symbol else None,
            "start": _iso(since),
            "limit": limit,
        }
        rows = self._paged("private_get_odr_orders", query, params)
        orders = [parse.parse_order(row) for row in rows]
        return sorted(orders, key=lambda o: (o["timestamp"] or 0, int(o["id"])))

    def fetch_open_orders(
        self,
        symbol: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[Order]:
        return self.fetch_orders(
            symbol, since, limit, {**(params or {}), "state": ["initial", "active"]}
        )

    def fetch_closed_orders(
        self,
        symbol: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[Order]:
        """Closed orders from the last 7 days. Older ones: ``fetch_order_history()``."""
        return self.fetch_orders(symbol, since, limit, {**(params or {}), "state": "closed"})

    def cancel_order(self, id: str | int, symbol: str | None = None) -> dict[str, Any]:
        """Ask the engine to cancel. Success means the request was accepted; the order
        closes shortly after (watch it with ``fetch_order`` or ``watch_orders``)."""
        self.request("private_delete_odr_orders_id", {"id": id})
        return {"id": str(id), "clientOrderId": None, "info": None}

    def cancel_order_by_identifier(self, identifier: str) -> dict[str, Any]:
        """Cancel by your ``clientOrderId``."""
        self.request(
            "private_delete_odr_orders_identifier_identifier", {"identifier": identifier}
        )
        return {"id": None, "clientOrderId": identifier, "info": None}

    def cancel_orders(
        self,
        ids: Sequence[str | int] | None = None,
        identifiers: Sequence[str] | None = None,
    ) -> CancelResult:
        """Cancel up to 10 orders, by ``ids`` or by ``identifiers`` (not both)."""
        if (ids is None) == (identifiers is None):
            raise errors.BadRequest("cancel_orders needs exactly one of ids or identifiers")
        values = [str(v) for v in (ids if ids is not None else identifiers or [])]
        if len(values) > CONSTANTS["bulk_orders_max"]:
            raise errors.BadRequest(
                f"cancel_orders takes at most {CONSTANTS['bulk_orders_max']} orders"
            )
        key = "ids" if ids is not None else "identifiers"
        raw = self.request("private_delete_odr_orders_bulk", body={key: values})
        return {
            "canceled": [str(v) for v in raw.get("canceled_orders", [])],
            "not_canceled": [str(v) for v in raw.get("not_canceled_orders", [])],
            "info": raw,
        }

    def fetch_my_trades(
        self,
        symbol: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[Trade]:
        """Your fills from the last 24 hours, oldest first. ``params``: ``side``, ``paginate``."""
        if (
            since is not None
            and since < (self._clock() - CONSTANTS["fills_max_age_seconds"]) * 1000
        ):
            raise errors.BadRequest("fetch_my_trades only covers the last 24 hours")
        query = {
            "symbol": to_market_id(symbol) if symbol else None,
            "start": since // 1000 if since is not None else None,
            "limit": limit,
        }
        rows = self._paged("private_get_odr_fills", query, params)
        trades = [parse.parse_my_trade(row) for row in rows]
        return sorted(trades, key=lambda t: (t["timestamp"] or 0, int(t["id"])))

    def fetch_order_history(
        self,
        symbol: str | None = None,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[Order]:
        """Closed orders with at least one fill, newest first (updated with a short delay).

        Range at most 90 days (default: the last month). ``params``: ``side``, ``type``,
        ``service``; ``paginate=True`` follows the cursor.
        """
        max_limit = CONSTANTS["order_history_max_limit"]
        if limit is not None and not 1 <= limit <= max_limit:
            raise errors.BadRequest(f"order history limit must be 1..{max_limit}")
        if since is not None and until is not None:
            if since >= until:
                raise errors.BadRequest("order history since must be before until")
            if until - since > CONSTANTS["order_history_max_range_days"] * 86_400_000:
                raise errors.BadRequest("order history range is at most 90 days")
        extra = dict(params or {})
        paginate = bool(extra.pop("paginate", False))
        filters = {
            "symbol": to_market_id(symbol) if symbol else None,
            "limit": limit,
            **extra,
        }
        query = {**filters, "start": since, "end": until}
        orders: list[Order] = []
        seen_ids: set[str] = set()
        seen_cursors: set[str] = set()
        while True:
            raw = self.request("private_get_odr_order_history", params=query)
            for row in raw.get("results", []):
                order = parse.parse_history_order(row)
                if order["id"] not in seen_ids:
                    seen_ids.add(order["id"])
                    orders.append(order)
            cursor = raw.get("next_cursor")
            if not (paginate and raw.get("has_next") and cursor) or cursor in seen_cursors:
                return orders
            seen_cursors.add(cursor)
            # The cursor replaces start/end; the server doesn't keep the other filters.
            query = {**filters, "cursor": raw["next_cursor"]}

    # --- wallet ------------------------------------------------------------------

    def fetch_balance(self, params: Mapping[str, Any] | None = None) -> Balances:
        """Balances of the ``main`` wallet (``params={"service": ...}`` for others).
        ``free`` is usable, ``used`` is frozen in orders or withdrawals."""
        query = {"service": "main", "limit": CONSTANTS["wallets_max_page_size"], **(params or {})}
        rows = self._all_pages("private_get_wlt_wallets", query)
        return parse.parse_balance(rows)

    def fetch_bank_accounts(self) -> list[BankAccount]:
        """Your bank accounts. Use an ``id`` as ``accountNumber`` when withdrawing IRT."""
        rows = self.request("private_get_wlt_account_numbers")
        return [parse.parse_bank_account(row) for row in rows]

    def fetch_deposit_address(
        self, code: str, network: str | None = None, params: Mapping[str, Any] | None = None
    ) -> DepositAddress:
        """Your deposit address for ``code`` on ``network`` (created on first use)."""
        network = network or (params or {}).get("network")
        if not network:
            raise errors.BadRequest("fetch_deposit_address needs a network code, e.g. 'TRX'")
        body = {"currency": code.upper(), "network": str(network).upper()}
        raw = self.request("private_post_wlt_address", body=body)
        return parse.parse_deposit_address(raw, body["network"])

    def fetch_currency_networks(self, code: str) -> list[Network]:
        """Networks of one currency, with deposit/withdraw availability."""
        rows = self.request(
            "private_get_wlt_networks", params={"currency_code": code.upper()}
        )
        return [parse.parse_currency_network(row) for row in rows]

    def fetch_deposits(
        self,
        code: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[Transaction]:
        """``params``: ``network``, ``state``, ``end``, ``is_crypto``, ``paginate``."""
        query = {"currency": code.upper() if code else None, "start": _iso(since), "limit": limit}
        rows = self._paged("private_get_wlt_deposits", query, params)
        return [parse.parse_deposit(row) for row in rows]

    def fetch_withdrawals(
        self,
        code: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[Transaction]:
        """``since`` is applied per day. ``params``: ``network``, ``state``, ``address``,
        ``identifier``, ``end`` (YYYY-MM-DD), ``paginate``."""
        start = _iso(since)
        query = {
            "currency": code.upper() if code else None,
            "start": start[:10] if start else None,
            "limit": limit,
        }
        rows = self._paged("private_get_wlt_withdraws", query, params)
        return [parse.parse_withdrawal(row) for row in rows]

    def withdraw(
        self,
        code: str,
        amount: Number,
        address: str | None = None,
        tag: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Transaction:
        """Create a withdrawal. It is not sent until you confirm it with
        ``verify_withdraw_otp()`` (twice unless ``info["is_single_otp"]``).

        Crypto: ``address`` + ``params={"network": "TRX"}`` (+ ``tag`` for a memo).
        IRT: ``params={"accountNumber": <fetch_bank_accounts() id>}``.
        Internal transfer to a Bitpin user: ``params={"alternativeAddress": phone or email}``.
        """
        extra = dict(params or {})
        if (to_decimal(amount) or Decimal(0)) <= 0:
            raise errors.BadRequest("withdraw amount must be positive")
        network = extra.pop("network", None)
        account = extra.pop("accountNumber", extra.pop("account_number", None))
        alternative = extra.pop("alternativeAddress", extra.pop("alternative_address", None))
        body: dict[str, Any] = {"currency": code.upper(), "amount": amount}
        if alternative:
            body["alternative_address"] = alternative
        elif account is not None:
            body["account_number"] = str(account)
        elif address:
            if not network:
                raise errors.BadRequest("crypto withdrawals need params={'network': <code>}")
            body.update(address=address, network=str(network).upper())
            if tag:
                body["memo"] = tag
        else:
            raise errors.BadRequest(
                "withdraw needs an address, params['accountNumber'] or params['alternativeAddress']"
            )
        body.update(extra)
        return parse.parse_withdrawal(self.request("private_post_wlt_withdraws", body=body))

    def verify_withdraw_otp(
        self, id: str | int, otp: str, second: bool = False
    ) -> dict[str, Any]:
        """Confirm a withdrawal. First OTP: your authenticator app. Second: the code sent to you."""
        body = {"otp": otp, "is_second_otp": second}
        result: dict[str, Any] = self.request(
            "private_post_wlt_withdraws_verify_otp_id", {"id": id}, body=body
        )
        return result

    def resend_withdraw_otp(
        self, id: str | int, first: bool = True, voice_call: bool = False
    ) -> dict[str, Any]:
        """Send the OTP of a withdrawal in the ``initial`` state again."""
        body = {"first": first, "use_voice_call": voice_call}
        result: dict[str, Any] = self.request(
            "private_post_wlt_withdraws_retry_id", {"id": id}, body=body
        )
        return result

    # --- pagination --------------------------------------------------------------

    def _paged(
        self, endpoint_id: str, query: Mapping[str, Any], params: Mapping[str, Any] | None
    ) -> list[Any]:
        merged = {**query, **(params or {})}
        if merged.pop("paginate", False):
            return self._all_pages(endpoint_id, merged)
        merged.pop("maxPages", None)
        rows: list[Any] = self.request(endpoint_id, params=merged)
        return rows

    def _all_pages(self, endpoint_id: str, query: Mapping[str, Any]) -> list[Any]:
        """Walk an id-cursor list: ``offset`` means "ids below this", not a row count."""
        query = dict(query)
        max_pages = int(query.pop("maxPages", 100))
        if query.get("limit") is None:
            query["limit"] = CONSTANTS[_MAX_PAGE_SIZE[endpoint_id]]
        limit = int(query["limit"])
        rows: list[Any] = []
        offset: int | None = None
        for _ in range(max_pages):
            page = self.request(endpoint_id, params=query)
            lowest = min((int(row["id"]) for row in page), default=None)
            if lowest is None or (offset is not None and lowest >= offset):
                break  # empty page, or the server didn't move past the last page
            rows.extend(page)
            if len(page) < limit:
                break
            offset = query["offset"] = lowest
        return rows

    # --- websocket -------------------------------------------------------

    def _websocket(self) -> Any:
        if self._ws is None:
            self._ws = websocket(self, self._ws_factory)
        return self._ws

    def watch_ticker(self, symbol: str) -> Ticker:
        """Wait for the next 24h ticker update of ``symbol``."""
        result: Ticker = self._websocket().watch_ticker(symbol)
        return result

    def watch_ohlcv(self, symbol: str, timeframe: str = "1m") -> list[OHLCV]:
        """Wait for the next candles of ``timeframe``."""
        result: list[OHLCV] = self._websocket().watch_ohlcv(symbol, timeframe)
        return result

    def watch_order_book(self, symbol: str) -> OrderBook:
        """Wait for the next order-book update of ``symbol``."""
        result: OrderBook = self._websocket().watch_order_book(symbol)
        return result

    def watch_trades(self, symbol: str) -> list[Trade]:
        """Wait for the next public trades of ``symbol``."""
        result: list[Trade] = self._websocket().watch_trades(symbol)
        return result

    def watch_orders(self, symbol: str | None = None) -> Order:
        """Wait for the next update of one of your orders."""
        result: Order = self._websocket().watch_orders(symbol)
        return result

    def watch_my_trades(self, symbol: str | None = None) -> Trade:
        """Wait for your next fill."""
        result: Trade = self._websocket().watch_my_trades(symbol)
        return result

    # --- not offered by Bitpin yet ---------------------------------------------------

    def cancel_all_orders(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("cancelAllOrders")

    def edit_order(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("editOrder")

    def fetch_accounts(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("fetchAccounts")

    def fetch_ledger(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("fetchLedger")

    def transfer(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("transfer")

    def fetch_deposit_withdraw_fees(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("fetchDepositWithdrawFees")

    def fetch_positions(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("fetchPositions")

    def set_leverage(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("setLeverage")

    def create_deposit_address(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("createDepositAddress")

    def watch_balance(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("watchBalance")

    def watch_tickers(self, *args: Any, **kwargs: Any) -> Any:
        raise not_supported("watchTickers")

    def set_sandbox_mode(self, enabled: bool) -> None:
        raise not_supported("sandbox")


_ORDER_TYPES = ("limit", "market", "stop_limit", "oco")
_PARAM_ALIASES = {
    "clientOrderId": "identifier",
    "stopPrice": "stop_price",
    "triggerPrice": "stop_price",
    "takeProfitPrice": "oco_target_price",
    "ocoTargetPrice": "oco_target_price",
    "quoteAmount": "quote_amount",
    "cost": "quote_amount",
}


def _positive(name: str, value: Any) -> None:
    number = to_decimal(value)
    if number is not None and number <= 0:
        raise errors.InvalidOrder(f"{name} must be positive")


def order_body(
    symbol: str,
    type: str,
    side: str,
    amount: Number | None,
    price: Number | None,
    params: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate an order locally and build the request body. Raises ``InvalidOrder``."""
    if type not in _ORDER_TYPES:
        raise errors.InvalidOrder(f"order type must be one of {', '.join(_ORDER_TYPES)}")
    if side not in ("buy", "sell"):
        raise errors.InvalidOrder("order side must be 'buy' or 'sell'")
    extra: dict[str, Any] = {}
    for key, value in (params or {}).items():
        name = _PARAM_ALIASES.get(key, key)
        if name in extra and extra[name] != value:
            raise errors.InvalidOrder(f"params set {name} twice ({key!r}); pass only one of both")
        extra[name] = value
    body: dict[str, Any] = {"symbol": to_market_id(symbol), "type": type, "side": side}
    if amount is not None:
        body["base_amount"] = amount
    if price is not None and type != "market":
        body["price"] = price
    body.update({k: v for k, v in extra.items() if v is not None})
    _positive("amount", body.get("base_amount"))
    _positive("price", body.get("price"))
    _positive("params['stopPrice']", body.get("stop_price"))
    _positive("params['takeProfitPrice']", body.get("oco_target_price"))
    _positive("params['quoteAmount']", body.get("quote_amount"))

    if type == "market":
        if "base_amount" in body and "quote_amount" in body:
            raise errors.InvalidOrder("market orders take only one of amount or quoteAmount")
        if "base_amount" not in body and "quote_amount" not in body:
            raise errors.InvalidOrder("market orders need amount or params['quoteAmount']")
        return body
    if "base_amount" not in body:
        raise errors.InvalidOrder(f"{type} orders need an amount")
    if "price" not in body:
        raise errors.InvalidOrder(f"{type} orders need a price")
    if type in ("stop_limit", "oco") and "stop_price" not in body:
        raise errors.InvalidOrder(f"{type} orders need params['stopPrice']")
    if type == "oco" and "oco_target_price" not in body:
        raise errors.InvalidOrder("oco orders need params['takeProfitPrice']")
    return body


def _iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


#: Page size used by ``paginate=True`` when the caller gives no ``limit``.
_MAX_PAGE_SIZE = {
    "private_get_odr_orders": "orders_max_page_size",
    "private_get_odr_fills": "fills_max_page_size",
    "private_get_wlt_wallets": "wallets_max_page_size",
    "private_get_wlt_deposits": "wallet_lists_max_page_size",
    "private_get_wlt_withdraws": "wallet_lists_max_page_size",
}

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


__all__ = ["TIMEFRAMES", "Bitpin", "not_supported"]
