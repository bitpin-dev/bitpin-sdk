"""Turn WebSocket publications into ccxt-shaped dicts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bitpin_sdk._core import parse
from bitpin_sdk._core.numbers import to_decimal
from bitpin_sdk._core.symbols import to_symbol
from bitpin_sdk.types import OHLCV, Order, OrderBook, Ticker, Trade


def _ms(value: Any) -> int | None:
    number = to_decimal(value) if value not in (None, "") else None
    return None if number is None else int(number)


def parse_ticker(data: Mapping[str, Any]) -> Ticker:
    """``currency_price_update``: 24h stats; ``change`` is a ratio, ``time`` is in ms."""
    timestamp = _ms(data.get("time"))
    last = to_decimal(data.get("price"))
    return {
        "symbol": to_symbol(str(data["symbol"])),
        "timestamp": timestamp,
        "datetime": parse.ms_to_iso(timestamp),
        "high": to_decimal(data.get("max")),
        "low": to_decimal(data.get("min")),
        "bid": None,
        "ask": None,
        "last": last,
        "close": last,
        "open": None,
        "change": None,
        "percentage": parse.ratio_to_percent(data.get("change")),
        "average": to_decimal(data.get("mean")),
        "baseVolume": to_decimal(data.get("amount")),
        "quoteVolume": to_decimal(data.get("value")),
        "info": dict(data),
    }


def parse_ohlcv(data: Mapping[str, Any], timeframe: str) -> list[OHLCV]:
    """``candle_update`` carries the latest candles of every resolution; keep one."""
    return [
        parse.parse_ohlcv(c) for c in data.get("candles", []) if c.get("resolution") == timeframe
    ]


def parse_order_book(data: Mapping[str, Any]) -> OrderBook:
    return parse.parse_order_book(
        data, to_symbol(str(data["symbol"])), parse.iso_to_ms(data.get("event_time"))
    )


def parse_trades(data: Mapping[str, Any]) -> list[Trade]:
    symbol = to_symbol(str(data["symbol"]))
    return [parse.parse_trade(row, symbol) for row in data.get("matches", [])]


def parse_order(data: Mapping[str, Any]) -> Order:
    return parse.parse_order(data)


def parse_my_trade(data: Mapping[str, Any]) -> Trade:
    return parse.parse_my_trade(data)
