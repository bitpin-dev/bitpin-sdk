"""Result types. Field names follow ccxt's unified structures; numbers are ``Decimal``.

Every result keeps the raw server response under ``info``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, TypedDict

OrderStatus = Literal["open", "closed", "canceled"]
TransactionStatus = Literal["pending", "ok", "failed", "canceled"]


class MinMax(TypedDict):
    min: Decimal | None
    max: Decimal | None


class Limits(TypedDict):
    amount: MinMax
    price: MinMax
    cost: MinMax


class Precision(TypedDict):
    amount: Decimal
    price: Decimal
    cost: Decimal


class Market(TypedDict):
    id: str
    symbol: str
    base: str
    quote: str
    baseId: str
    quoteId: str
    active: bool
    type: Literal["spot"]
    spot: bool
    margin: bool
    swap: bool
    future: bool
    option: bool
    contract: bool
    precision: Precision
    limits: Limits
    info: dict[str, Any]


class Currency(TypedDict):
    id: str
    code: str
    name: str
    active: bool
    precision: Decimal
    info: dict[str, Any]


class Ticker(TypedDict):
    symbol: str
    timestamp: int | None
    datetime: str | None
    high: Decimal | None
    low: Decimal | None
    bid: Decimal | None
    ask: Decimal | None
    last: Decimal | None
    close: Decimal | None
    open: Decimal | None
    change: Decimal | None
    percentage: Decimal | None
    average: Decimal | None
    baseVolume: Decimal | None
    quoteVolume: Decimal | None
    info: dict[str, Any]


class OrderBook(TypedDict):
    symbol: str
    bids: list[list[Decimal]]
    asks: list[list[Decimal]]
    timestamp: int | None
    datetime: str | None
    nonce: int | None


class Fee(TypedDict):
    cost: Decimal | None
    currency: str | None


class Trade(TypedDict):
    id: str
    order: str | None
    timestamp: int | None
    datetime: str | None
    symbol: str
    type: str | None
    side: str
    takerOrMaker: str | None
    price: Decimal | None
    amount: Decimal | None
    cost: Decimal | None
    fee: Fee | None
    info: dict[str, Any]


class Order(TypedDict):
    id: str
    clientOrderId: str | None
    timestamp: int | None
    datetime: str | None
    lastTradeTimestamp: int | None
    symbol: str
    type: str
    timeInForce: str | None
    side: str
    price: Decimal | None
    stopPrice: Decimal | None
    triggerPrice: Decimal | None
    takeProfitPrice: Decimal | None
    average: Decimal | None
    amount: Decimal | None
    cost: Decimal | None
    filled: Decimal | None
    remaining: Decimal | None
    status: str
    fee: Fee
    trades: list[Trade]
    reduceOnly: bool | None
    postOnly: bool | None
    info: dict[str, Any]


class BalanceEntry(TypedDict):
    free: Decimal
    used: Decimal
    total: Decimal


class TradingFee(TypedDict):
    symbol: str
    maker: Decimal | None
    taker: Decimal | None
    percentage: bool
    tierBased: bool
    info: dict[str, Any]


class Transaction(TypedDict):
    id: str
    txid: str | None
    timestamp: int | None
    datetime: str | None
    network: str | None
    address: str | None
    addressTo: str | None
    tag: str | None
    type: Literal["deposit", "withdrawal"]
    amount: Decimal | None
    currency: str
    status: str
    updated: int | None
    fee: Fee | None
    internal: bool | None
    comment: str | None
    info: dict[str, Any]


class DepositAddress(TypedDict):
    currency: str
    network: str | None
    address: str
    tag: str | None
    info: dict[str, Any]


class Network(TypedDict):
    id: str
    network: str
    name: str
    deposit: bool
    withdraw: bool
    addressPattern: str | None
    info: dict[str, Any]


class BankAccount(TypedDict):
    id: str
    currency: str | None
    iban: str | None
    card: str | None
    status: str
    info: dict[str, Any]


class CancelResult(TypedDict):
    canceled: list[str]
    not_canceled: list[str]
    info: dict[str, Any]


#: ``fetch_balance()`` result: ``{"BTC": BalanceEntry, ..., "free": {...}, "used": {...},
#: "total": {...}, "info": [...]}``, as in ccxt.
Balances = dict[str, Any]
#: ``[timestamp_ms, open, high, low, close, volume]``
OHLCV = list[Any]
