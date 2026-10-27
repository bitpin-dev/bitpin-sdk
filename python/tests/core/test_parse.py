"""Parsers turn Bitpin responses (the shared fixtures) into ccxt-shaped dicts."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from bitpin_sdk._core import parse
from tests.fixtures import body

T_ORDER = 1793083530123  # 2026-10-27T10:15:30.123456+03:30 in ms


def test_parse_iso_datetime_to_ms() -> None:
    assert parse.iso_to_ms("2026-10-27T10:15:30.123456+03:30") == T_ORDER
    assert parse.iso_to_ms("2025-10-19T11:38:27.929164Z") == 1760873907929
    assert parse.iso_to_ms("2026-10-27T10:20:00.5+03:30") == 1793083800500
    assert parse.iso_to_ms(None) is None
    assert parse.iso_to_ms("garbage") is None


def test_ms_to_iso() -> None:
    assert parse.ms_to_iso(T_ORDER) == "2026-10-27T06:45:30.123Z"
    assert parse.ms_to_iso(None) is None


def test_parse_market() -> None:
    m = parse.parse_market(body("public_get_mkt_markets")[0])
    assert m["id"] == "BTC_IRT"
    assert m["symbol"] == "BTC/IRT"
    assert (m["base"], m["quote"], m["baseId"], m["quoteId"]) == ("BTC", "IRT", "BTC", "IRT")
    assert m["active"] is True
    assert m["type"] == "spot"
    assert m["spot"] is True
    assert m["precision"] == {"amount": D("1E-8"), "price": D("1"), "cost": D("1")}
    assert m["limits"]["amount"] == {"min": None, "max": None}
    assert m["info"]["name"] == "Bitcoin/Toman"


def test_suspended_market_is_inactive() -> None:
    m = parse.parse_market(body("public_get_mkt_markets")[2])
    assert m["active"] is False
    assert m["precision"]["price"] == D("0.01")


def test_parse_currency() -> None:
    c = parse.parse_currency(body("public_get_mkt_currencies")[1])
    assert c["id"] == "BTC"
    assert c["code"] == "BTC"
    assert c["name"] == "Bitcoin"
    assert c["active"] is True
    assert c["precision"] == D("1E-8")


def test_parse_ticker() -> None:
    t = parse.parse_ticker(body("public_get_mkt_tickers")[0])
    assert t["symbol"] == "BTC/IRT"
    assert t["last"] == D("3145737420")
    assert t["close"] == D("3145737420")
    assert t["high"] == D("3200000000")
    assert t["low"] == D("3100000000")
    assert t["percentage"] == D("-1.58")
    assert t["change"] is None
    assert t["timestamp"] == 1761550530189
    assert t["datetime"] == "2025-10-27T07:35:30.189Z"
    assert t["baseVolume"] is None


def test_parse_ticker_with_nulls() -> None:
    t = parse.parse_ticker(body("public_get_mkt_tickers")[1])
    assert t["high"] is None
    assert t["low"] is None


def test_parse_order_book_sorts_sides() -> None:
    raw = {"asks": [["3", "1"], ["2", "1"]], "bids": [["1", "1"], ["1.5", "2"]]}
    ob = parse.parse_order_book(raw, "BTC/IRT")
    assert ob["asks"] == [[D("2"), D("1")], [D("3"), D("1")]]
    assert ob["bids"] == [[D("1.5"), D("2")], [D("1"), D("1")]]
    assert ob["symbol"] == "BTC/IRT"
    assert ob["nonce"] is None


def test_parse_public_trade() -> None:
    t = parse.parse_trade(body("public_get_mth_matches_symbol")[0], "BTC/IRT")
    assert t["id"] == "73802972_73807087"
    assert t["side"] == "buy"
    assert t["price"] == D("3145737420")
    assert t["amount"] == D("0.002")
    assert t["cost"] == D("6291474.84")
    assert t["timestamp"] == 1761550530149
    assert t["symbol"] == "BTC/IRT"


def test_parse_my_trade() -> None:
    t = parse.parse_my_trade(body("private_get_odr_fills")[0])
    assert t["id"] == "65375307"
    assert t["order"] == "535179300"
    assert t["symbol"] == "BTC/IRT"
    assert t["fee"] == {"cost": D("11060"), "currency": "IRT"}
    assert t["timestamp"] == 1793083800500


def test_parse_ohlcv() -> None:
    row = parse.parse_ohlcv(body("public_get_mkt_candles")[0])
    assert row == [
        1761550200000,
        D("3100000000"),
        D("3120000000"),
        D("3090000000"),
        D("3110000000"),
        D("1.25"),
    ]


def test_parse_open_order() -> None:
    o = parse.parse_order(body("private_post_odr_orders"))
    assert o["id"] == "535179385"
    assert o["clientOrderId"] == "mm-bid-1"
    assert o["symbol"] == "BTC/IRT"
    assert (o["type"], o["side"], o["status"]) == ("limit", "buy", "open")
    assert o["price"] == D("3100000000")
    assert o["amount"] == D("0.001")
    assert o["filled"] == D("0")
    assert o["remaining"] == D("0.001")
    assert o["cost"] == D("0")
    assert o["average"] is None
    assert o["timestamp"] == T_ORDER
    assert o["lastTradeTimestamp"] is None
    assert o["fee"] == {"cost": D("0"), "currency": None}
    assert o["trades"] == []


def test_parse_filled_order() -> None:
    o = parse.parse_order(body("private_get_odr_orders")[1])
    assert o["status"] == "closed"
    assert o["filled"] == D("0.001")
    assert o["remaining"] == D("0")
    assert o["average"] == D("3160000000")
    assert o["cost"] == D("3160000")


@pytest.mark.parametrize(
    ("state", "base", "dealed_base", "quote", "dealed_quote", "status"),
    [
        ("initial", "1", "0", "10", "0", "open"),
        ("active", "1", "0.5", "10", "5", "open"),
        ("closed", "1", "1", "10", "10", "closed"),
        ("closed", "1", "0.5", "10", "5", "canceled"),
        ("closed", "1", "0", "10", "0", "canceled"),
        ("closed", None, "0.3", "10", "10", "closed"),
        ("closed", None, "0.3", "10", "9", "canceled"),
        ("weird", "1", "0", "10", "0", "weird"),
    ],
)
def test_order_status_rule(
    state: str, base: str | None, dealed_base: str, quote: str, dealed_quote: str, status: str
) -> None:
    raw = {
        **body("private_post_odr_orders"),
        "state": state,
        "base_amount": base,
        "dealed_base_amount": dealed_base,
        "quote_amount": quote,
        "dealed_quote_amount": dealed_quote,
    }
    assert parse.parse_order(raw)["status"] == status


def test_stop_and_oco_prices() -> None:
    raw = {
        **body("private_post_odr_orders"),
        "type": "oco",
        "stop_price": "58000",
        "oco_target_price": "70000",
    }
    o = parse.parse_order(raw)
    assert o["stopPrice"] == D("58000")
    assert o["triggerPrice"] == D("58000")
    assert o["takeProfitPrice"] == D("70000")


def test_parse_history_order_uses_ms_times() -> None:
    o = parse.parse_history_order(body("private_get_odr_order_history")["results"][0])
    assert o["id"] == "535100000"
    assert o["type"] == "market"
    assert o["status"] == "closed"
    assert o["timestamp"] == 1761460000000
    assert o["lastTradeTimestamp"] == 1761460000500
    assert o["average"] == D("3100000000")
    assert o["price"] is None


def test_parse_bulk_orders_accepts_both_shapes() -> None:
    wrapped = body("private_post_odr_orders_bulk")
    assert [o["id"] for o in parse.parse_bulk_orders(wrapped)] == ["535179385", "535179386"]
    assert [o["id"] for o in parse.parse_bulk_orders(wrapped["orders"])] == [
        "535179385",
        "535179386",
    ]


def test_parse_balance() -> None:
    b = parse.parse_balance(body("private_get_wlt_wallets"))
    assert b["BTC"] == {"free": D("0.0125"), "used": D("0.001"), "total": D("0.0135")}
    assert b["free"]["IRT"] == D("150000000")
    assert b["used"]["IRT"] == D("3100000")
    assert b["total"]["USDT"] == D("0")
    assert len(b["info"]) == 3


def test_parse_balance_sums_repeated_assets() -> None:
    rows = [
        {"asset": "BTC", "balance": "1", "frozen": "0"},
        {"asset": "BTC", "balance": "2", "frozen": "1"},
    ]
    assert parse.parse_balance(rows)["BTC"] == {"free": D("3"), "used": D("1"), "total": D("4")}


def test_parse_trading_fee_converts_percent_to_ratio() -> None:
    f = parse.parse_trading_fee(body("private_get_mkt_commissions")[0])
    assert f == {
        "symbol": "BTC/IRT",
        "maker": D("0.003"),
        "taker": D("0.0035"),
        "percentage": True,
        "tierBased": True,
        "info": body("private_get_mkt_commissions")[0],
    }


def test_parse_deposit() -> None:
    d = parse.parse_deposit(body("private_get_wlt_deposits")[0])
    assert d["id"] == "9001"
    assert d["type"] == "deposit"
    assert d["currency"] == "USDT"
    assert d["amount"] == D("250.5")
    assert d["status"] == "ok"
    assert d["network"] == "TRX"
    assert d["txid"].startswith("0000")
    assert d["internal"] is False


@pytest.mark.parametrize(
    ("state", "status"), [("succeed", "ok"), ("failed", "failed"), ("waiting", "pending")]
)
def test_deposit_status(state: str, status: str) -> None:
    raw = {**body("private_get_wlt_deposits")[0], "state": state}
    assert parse.parse_deposit(raw)["status"] == status


def test_parse_crypto_withdrawal() -> None:
    w = parse.parse_withdrawal(body("private_get_wlt_withdraws")[0])
    assert w["id"] == "7001"
    assert w["type"] == "withdrawal"
    assert w["status"] == "ok"
    assert w["address"] == "TTestAddressDoNotUse000000000000000"
    assert w["addressTo"] == w["address"]
    assert w["network"] == "TRX"
    assert w["fee"] == {"cost": D("1"), "currency": "USDT"}
    assert w["updated"] == parse.iso_to_ms("2026-10-25T12:30:00+03:30")


def test_parse_irt_withdrawal() -> None:
    w = parse.parse_withdrawal(body("private_get_wlt_withdraws")[1])
    assert w["status"] == "pending"
    assert w["address"] is None
    assert w["network"] is None


@pytest.mark.parametrize(
    ("state", "status"),
    [
        ("canceled", "canceled"),
        ("failed", "failed"),
        ("initial", "pending"),
        ("suspicious", "pending"),
    ],
)
def test_withdrawal_status(state: str, status: str) -> None:
    raw = {**body("private_get_wlt_withdraws")[0], "state": state}
    assert parse.parse_withdrawal(raw)["status"] == status


def test_parse_withdraw_create_keeps_single_otp_flag() -> None:
    w = parse.parse_withdrawal(body("private_post_wlt_withdraws"))
    assert w["status"] == "pending"
    assert w["info"]["is_single_otp"] is False


def test_parse_deposit_address() -> None:
    a = parse.parse_deposit_address(body("private_post_wlt_address"), network="TRX")
    assert a["currency"] == "USDT"
    assert a["network"] == "TRX"
    assert a["address"] == "TTestAddressDoNotUse000000000000000"
    assert a["tag"] is None


def test_parse_currency_network_accepts_v1_and_v2_shapes() -> None:
    v2, v1 = body("private_get_wlt_networks")
    n2 = parse.parse_currency_network(v2)
    assert n2["network"] == "TRX"
    assert n2["deposit"] is True
    assert n2["withdraw"] is False
    assert n2["addressPattern"] is None
    n1 = parse.parse_currency_network(v1)
    assert n1["network"] == "ETH"
    assert n1["addressPattern"] == "^0x[a-fA-F0-9]{40}$"


def test_parse_network() -> None:
    n = parse.parse_network(body("public_get_mkt_networks")[1])
    assert n["network"] == "TRX"
    assert n["name"] == "Tron"
    assert n["withdraw"] is False


def test_parse_bank_account() -> None:
    a = parse.parse_bank_account(body("private_get_wlt_account_numbers")[0])
    assert a == {
        "id": "123",
        "currency": "IRT",
        "iban": "IR000000000000000000000000",
        "card": "000000******0000",
        "status": "verified",
        "info": body("private_get_wlt_account_numbers")[0],
    }
