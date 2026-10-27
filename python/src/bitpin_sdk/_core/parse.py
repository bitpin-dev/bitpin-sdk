"""Turn Bitpin responses into ccxt-shaped dicts. Pure: no I/O."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from bitpin_sdk._core.numbers import to_decimal
from bitpin_sdk._core.symbols import to_symbol
from bitpin_sdk.types import (
    OHLCV,
    Balances,
    BankAccount,
    Currency,
    DepositAddress,
    Fee,
    Market,
    Network,
    Order,
    OrderBook,
    Ticker,
    Trade,
    TradingFee,
    Transaction,
)

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


def _dec(value: Any) -> Decimal | None:
    try:
        return to_decimal(value)
    except ValueError:
        return None


def _str(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def iso_to_ms(value: str | None) -> int | None:
    """``2026-10-27T10:15:30.123456+03:30`` or ``...Z`` → Unix milliseconds."""
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        # Python 3.10 only accepts 3- or 6-digit fractions.
        head, dot, rest = text.partition(".")
        if not dot:
            return None
        digits = "".join(c for c in rest if c.isdigit())
        offset = rest[len(digits) :]
        try:
            parsed = datetime.fromisoformat(f"{head}.{digits[:6].ljust(6, '0')}{offset}")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def seconds_to_ms(value: Any) -> int | None:
    number = _dec(value)
    return None if number is None else int(number * 1000)


def ms_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    moment = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value % 1000:03d}Z"


def _tick(places: Any) -> Decimal:
    return Decimal(1).scaleb(-int(places or 0))


def _no_limit() -> dict[str, None]:
    return {"min": None, "max": None}


def parse_market(raw: Mapping[str, Any]) -> Market:
    market_id = str(raw["symbol"])
    base, quote = str(raw["base"]), str(raw["quote"])
    return {
        "id": market_id,
        "symbol": f"{base}/{quote}",
        "base": base,
        "quote": quote,
        "baseId": base,
        "quoteId": quote,
        "active": bool(raw.get("tradable")) and not raw.get("suspended", False),
        "type": "spot",
        "spot": True,
        "margin": False,
        "swap": False,
        "future": False,
        "option": False,
        "contract": False,
        "precision": {
            "amount": _tick(raw.get("base_amount_precision")),
            "price": _tick(raw.get("price_precision")),
            "cost": _tick(raw.get("quote_amount_precision")),
        },
        "limits": {"amount": _no_limit(), "price": _no_limit(), "cost": _no_limit()},  # type: ignore[typeddict-item]
        "info": dict(raw),
    }


def parse_currency(raw: Mapping[str, Any]) -> Currency:
    code = str(raw["currency"])
    return {
        "id": code,
        "code": code,
        "name": str(raw.get("name") or code),
        "active": bool(raw.get("tradable")),
        "precision": _tick(raw.get("precision")),
        "info": dict(raw),
    }


def parse_ticker(raw: Mapping[str, Any]) -> Ticker:
    timestamp = seconds_to_ms(raw.get("timestamp"))
    last = _dec(raw.get("price"))
    return {
        "symbol": to_symbol(str(raw["symbol"])),
        "timestamp": timestamp,
        "datetime": ms_to_iso(timestamp),
        "high": _dec(raw.get("high")),
        "low": _dec(raw.get("low")),
        "bid": None,
        "ask": None,
        "last": last,
        "close": last,
        "open": None,
        "change": None,
        "percentage": _dec(raw.get("daily_change_price")),
        "average": _dec(raw.get("mean")),
        "baseVolume": _dec(raw.get("base_volume")),
        "quoteVolume": _dec(raw.get("quote_volume")),
        "info": dict(raw),
    }


def _levels(rows: Iterable[Any], reverse: bool) -> list[list[Decimal]]:
    levels = [[Decimal(str(price)), Decimal(str(amount))] for price, amount, *_ in rows]
    return sorted(levels, key=lambda level: level[0], reverse=reverse)


def parse_order_book(
    raw: Mapping[str, Any], symbol: str, timestamp: int | None = None
) -> OrderBook:
    return {
        "symbol": symbol,
        "bids": _levels(raw.get("bids") or [], reverse=True),
        "asks": _levels(raw.get("asks") or [], reverse=False),
        "timestamp": timestamp,
        "datetime": ms_to_iso(timestamp),
        "nonce": None,
    }


def parse_trade(raw: Mapping[str, Any], symbol: str) -> Trade:
    timestamp = seconds_to_ms(raw.get("time"))
    return {
        "id": str(raw["id"]),
        "order": None,
        "timestamp": timestamp,
        "datetime": ms_to_iso(timestamp),
        "symbol": symbol,
        "type": None,
        "side": str(raw.get("side")),
        "takerOrMaker": None,
        "price": _dec(raw.get("price")),
        "amount": _dec(raw.get("base_amount")),
        "cost": _dec(raw.get("quote_amount")),
        "fee": None,
        "info": dict(raw),
    }


def parse_my_trade(raw: Mapping[str, Any]) -> Trade:
    timestamp = iso_to_ms(raw.get("created_at"))
    return {
        "id": str(raw["id"]),
        "order": _str(raw.get("order_id")),
        "timestamp": timestamp,
        "datetime": ms_to_iso(timestamp),
        "symbol": to_symbol(str(raw["symbol"])),
        "type": None,
        "side": str(raw.get("side")),
        "takerOrMaker": None,
        "price": _dec(raw.get("price")),
        "amount": _dec(raw.get("base_amount")),
        "cost": _dec(raw.get("quote_amount")),
        "fee": {
            "cost": _dec(raw.get("commission")),
            "currency": _str(raw.get("commission_currency")),
        },
        "info": dict(raw),
    }


def parse_ohlcv(raw: Mapping[str, Any]) -> OHLCV:
    return [
        seconds_to_ms(raw.get("ts")),
        _dec(raw.get("open")),
        _dec(raw.get("high")),
        _dec(raw.get("low")),
        _dec(raw.get("close")),
        _dec(raw.get("volume")),
    ]


def _order_status(raw: Mapping[str, Any]) -> str:
    state = str(raw.get("state"))
    if state in ("initial", "active"):
        return "open"
    if state != "closed":
        return state
    base, dealed_base = _dec(raw.get("base_amount")), _dec(raw.get("dealed_base_amount")) or _ZERO
    if base is not None and base > 0:
        return "closed" if dealed_base >= base else "canceled"
    quote, dealed_quote = (
        _dec(raw.get("quote_amount")),
        _dec(raw.get("dealed_quote_amount")) or _ZERO,
    )
    if quote is not None and quote > 0:
        return "closed" if dealed_quote >= quote else "canceled"
    return "closed"


def _positive(value: Decimal | None) -> Decimal | None:
    return value if value is not None and value > 0 else None


def _order(raw: Mapping[str, Any], timestamp: int | None, closed: int | None, status: str) -> Order:
    amount = _dec(raw.get("base_amount"))
    filled = _dec(raw.get("dealed_base_amount"))
    remaining = None if amount is None else max(amount - (filled or _ZERO), _ZERO)
    stop = _dec(raw.get("stop_price"))
    fee: Fee = {"cost": _dec(raw.get("commission")), "currency": None}
    return {
        "id": str(raw["id"]),
        "clientOrderId": _str(raw.get("identifier")),
        "timestamp": timestamp,
        "datetime": ms_to_iso(timestamp),
        "lastTradeTimestamp": closed if filled else None,
        "symbol": to_symbol(str(raw["symbol"])),
        "type": str(raw.get("type")),
        "timeInForce": None,
        "side": str(raw.get("side")),
        "price": _positive(_dec(raw.get("price"))),
        "stopPrice": stop,
        "triggerPrice": stop,
        "takeProfitPrice": _dec(raw.get("oco_target_price")),
        "average": _positive(_dec(raw.get("average_price"))),
        "amount": amount,
        "cost": _dec(raw.get("dealed_quote_amount")),
        "filled": filled,
        "remaining": remaining,
        "status": status,
        "fee": fee,
        "trades": [],
        "reduceOnly": None,
        "postOnly": None,
        "info": dict(raw),
    }


def parse_order(raw: Mapping[str, Any]) -> Order:
    return _order(
        raw, iso_to_ms(raw.get("created_at")), iso_to_ms(raw.get("closed_at")), _order_status(raw)
    )


def parse_history_order(raw: Mapping[str, Any]) -> Order:
    """Order-history rows are always closed and use Unix-millisecond times."""
    created = raw.get("created_at")
    closed = raw.get("closed_at")
    status = _order_status({**raw, "state": "closed"})
    return _order(
        raw,
        int(created) if created is not None else None,
        int(closed) if closed is not None else None,
        status,
    )


def parse_bulk_orders(raw: Any) -> list[Order]:
    """Bulk create returns ``{"orders": [...]}``; older servers return a bare list."""
    rows = raw.get("orders", []) if isinstance(raw, Mapping) else raw or []
    return [parse_order(row) for row in rows]


def parse_balance(rows: Iterable[Mapping[str, Any]]) -> Balances:
    rows = list(rows)
    result: Balances = {"info": [dict(r) for r in rows], "free": {}, "used": {}, "total": {}}
    for row in rows:
        code = str(row["asset"])
        free = (_dec(row.get("balance")) or _ZERO) + result["free"].get(code, _ZERO)
        used = (_dec(row.get("frozen")) or _ZERO) + result["used"].get(code, _ZERO)
        result["free"][code], result["used"][code], result["total"][code] = free, used, free + used
        result[code] = {"free": free, "used": used, "total": free + used}
    return result


def parse_trading_fee(raw: Mapping[str, Any]) -> TradingFee:
    """Bitpin returns percents (``0.3`` = 0.3 %); ccxt uses ratios (``0.003``)."""
    maker, taker = _dec(raw.get("maker")), _dec(raw.get("taker"))
    return {
        "symbol": to_symbol(str(raw["symbol"])),
        "maker": None if maker is None else maker / _HUNDRED,
        "taker": None if taker is None else taker / _HUNDRED,
        "percentage": True,
        "tierBased": True,
        "info": dict(raw),
    }


_DEPOSIT_STATUS = {"succeed": "ok", "failed": "failed", "canceled": "canceled"}
_WITHDRAW_STATUS = {"succeed": "ok", "failed": "failed", "canceled": "canceled"}


def _network_code(value: Any) -> str | None:
    if isinstance(value, Mapping):
        return _str(value.get("code"))
    return _str(value)


def parse_deposit(raw: Mapping[str, Any]) -> Transaction:
    timestamp = iso_to_ms(raw.get("created_at"))
    currency = str(raw.get("currency"))
    return {
        "id": str(raw["id"]),
        "txid": _str(raw.get("tx_hash")),
        "timestamp": timestamp,
        "datetime": ms_to_iso(timestamp),
        "network": _network_code(raw.get("network")),
        "address": None,
        "addressTo": None,
        "tag": None,
        "type": "deposit",
        "amount": _dec(raw.get("amount")),
        "currency": currency,
        "status": _DEPOSIT_STATUS.get(str(raw.get("state")), "pending"),
        "updated": None,
        "fee": None,
        "internal": raw.get("internal"),
        "comment": _str(raw.get("description")),
        "info": dict(raw),
    }


def parse_withdrawal(raw: Mapping[str, Any]) -> Transaction:
    timestamp = iso_to_ms(raw.get("created_at"))
    crypto = raw.get("crypto_details") or {}
    currency = str(raw.get("currency"))
    address = _str(crypto.get("address"))
    return {
        "id": str(raw["id"]),
        "txid": _str(crypto.get("tx_hash")),
        "timestamp": timestamp,
        "datetime": ms_to_iso(timestamp),
        "network": _str(crypto.get("network")),
        "address": address,
        "addressTo": address,
        "tag": _str(crypto.get("memo")),
        "type": "withdrawal",
        "amount": _dec(raw.get("amount")),
        "currency": currency,
        "status": _WITHDRAW_STATUS.get(str(raw.get("state")), "pending"),
        "updated": iso_to_ms(raw.get("closed_at")),
        "fee": {"cost": _dec(raw.get("commission")), "currency": currency},
        "internal": raw.get("internal"),
        "comment": _str(raw.get("description")),
        "info": dict(raw),
    }


def parse_deposit_address(raw: Mapping[str, Any], network: str | None) -> DepositAddress:
    return {
        "currency": str(raw.get("currency")),
        "network": network,
        "address": str(raw.get("address")),
        "tag": _str(raw.get("memo")),
        "info": dict(raw),
    }


def parse_network(raw: Mapping[str, Any]) -> Network:
    code = str(raw["code"])
    return {
        "id": code,
        "network": code,
        "name": str(raw.get("title") or code),
        "deposit": bool(raw.get("can_deposit")),
        "withdraw": bool(raw.get("can_withdraw")),
        "addressPattern": _str(raw.get("address_pattern")),
        "info": dict(raw),
    }


def parse_currency_network(raw: Mapping[str, Any]) -> Network:
    """One row of the currency-networks list. Accepts the v1 and v2 ``network`` shapes."""
    network = parse_network(raw.get("network") or {})
    network["deposit"] = network["deposit"] and not raw.get("deposit_under_maintenance", False)
    network["withdraw"] = network["withdraw"] and not raw.get("withdraw_under_maintenance", False)
    network["info"] = dict(raw)
    return network


def parse_bank_account(raw: Mapping[str, Any]) -> BankAccount:
    currency = raw.get("currency")
    return {
        "id": str(raw["id"]),
        "currency": _str(currency.get("currency"))
        if isinstance(currency, Mapping)
        else _str(currency),
        "iban": _str(raw.get("iban")),
        "card": _str(raw.get("card")),
        "status": str(raw.get("state")),
        "info": dict(raw),
    }
