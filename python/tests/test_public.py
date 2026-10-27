"""Unified public market-data methods."""

from __future__ import annotations

from decimal import Decimal as D
from typing import Any

import pytest
import respx

from bitpin_sdk import errors
from tests.conftest import NOW, call, route


async def test_load_markets_caches(client: Any, mock: respx.MockRouter) -> None:
    markets = route(mock, "public_get_mkt_markets")
    result = await call(client.load_markets())
    await call(client.load_markets())
    assert markets.call_count == 1
    assert set(result) == {"BTC/IRT", "USDT/IRT", "ETH/USDT"}
    assert client.markets_by_id["BTC_IRT"]["symbol"] == "BTC/IRT"
    assert client.market("btc_irt")["id"] == "BTC_IRT"
    await call(client.load_markets(reload=True))
    assert markets.call_count == 2


async def test_market_unknown_symbol(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "public_get_mkt_markets")
    await call(client.load_markets())
    with pytest.raises(errors.BadSymbol, match="DOGE/IRT"):
        client.market("DOGE/IRT")


async def test_market_before_load_raises(client: Any) -> None:
    with pytest.raises(errors.BitpinError, match="load_markets"):
        client.market("BTC/IRT")


async def test_fetch_markets(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "public_get_mkt_markets")
    markets = await call(client.fetch_markets())
    assert [m["symbol"] for m in markets] == ["BTC/IRT", "USDT/IRT", "ETH/USDT"]


async def test_fetch_currencies(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "public_get_mkt_currencies")
    currencies = await call(client.fetch_currencies())
    assert currencies["BTC"]["precision"] == D("1E-8")


async def test_fetch_networks_passes_filters(client: Any, mock: respx.MockRouter) -> None:
    networks = route(mock, "public_get_mkt_networks")
    result = await call(client.fetch_networks({"can_deposit": True}))
    assert networks.calls.last.request.url.params["can_deposit"] == "true"
    assert [n["network"] for n in result] == ["BTC", "TRX"]


async def test_fetch_tickers_and_ticker(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "public_get_mkt_tickers")
    tickers = await call(client.fetch_tickers())
    assert set(tickers) == {"BTC/IRT", "USDT/IRT"}
    some = await call(client.fetch_tickers(["usdt/irt"]))
    assert set(some) == {"USDT/IRT"}
    ticker = await call(client.fetch_ticker("BTC_IRT"))
    assert ticker["last"] == D("3145737420")


async def test_fetch_ticker_unknown(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "public_get_mkt_tickers")
    with pytest.raises(errors.BadSymbol):
        await call(client.fetch_ticker("DOGE/IRT"))


async def test_fetch_order_book(client: Any, mock: respx.MockRouter) -> None:
    book = route(mock, "public_get_mth_orderbook_symbol", symbol="BTC_IRT")
    result = await call(client.fetch_order_book("BTC/IRT", limit=50))
    assert book.calls.last.request.url.path == "/api/v1/mth/orderbook/BTC_IRT/"
    assert book.calls.last.request.url.params["limit"] == "50"
    assert result["bids"][0] == [D("3140000000"), D("0.05")]
    assert result["asks"][0] == [D("3150000000"), D("0.01")]
    assert result["symbol"] == "BTC/IRT"


async def test_fetch_order_book_limit_over_max(client: Any) -> None:
    with pytest.raises(errors.BadRequest, match="50"):
        await call(client.fetch_order_book("BTC/IRT", limit=51))


async def test_fetch_trades_filters_since_and_limit(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "public_get_mth_matches_symbol", symbol="BTC_IRT")
    trades = await call(client.fetch_trades("BTC/IRT"))
    assert [t["id"] for t in trades] == ["73802970_73807080", "73802972_73807087"]
    recent = await call(client.fetch_trades("BTC/IRT", since=1761550510000))
    assert [t["id"] for t in recent] == ["73802972_73807087"]
    last = await call(client.fetch_trades("BTC/IRT", limit=1))
    assert [t["id"] for t in last] == ["73802972_73807087"]


async def test_fetch_ohlcv_with_since_and_limit(client: Any, mock: respx.MockRouter) -> None:
    candles = route(mock, "public_get_mkt_candles")
    rows = await call(client.fetch_ohlcv("BTC/IRT", "30m", since=1761550200000, limit=2))
    params = candles.calls.last.request.url.params
    assert params["symbol"] == "BTC_IRT"
    assert params["res"] == "30m"
    assert params["from"] == "1761550200"
    assert params["to"] == str(1761550200 + 2 * 1800)
    assert rows[0][0] == 1761550200000
    assert rows[1][4] == D("3145737420")


async def test_fetch_ohlcv_defaults_to_recent_500(client: Any, mock: respx.MockRouter) -> None:
    candles = route(mock, "public_get_mkt_candles")
    await call(client.fetch_ohlcv("BTC/IRT", "1h"))
    params = candles.calls.last.request.url.params
    assert params["to"] == str(int(NOW))
    assert params["from"] == str(int(NOW) - 500 * 3600)


async def test_fetch_ohlcv_trims_to_limit(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "public_get_mkt_candles")
    rows = await call(client.fetch_ohlcv("BTC/IRT", "30m", limit=1))
    assert len(rows) == 1
    assert rows[0][0] == 1761552000000


async def test_fetch_ohlcv_rejects_unknown_timeframe(client: Any) -> None:
    with pytest.raises(errors.BadRequest, match="timeframe '2h'"):
        await call(client.fetch_ohlcv("BTC/IRT", "2h"))


async def test_fetch_ohlcv_rejects_more_than_max(client: Any) -> None:
    with pytest.raises(errors.BadRequest, match="10000"):
        await call(client.fetch_ohlcv("BTC/IRT", "1m", limit=10001))


async def test_fetch_trading_fees(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "private_get_mkt_commissions")
    fees = await call(client.fetch_trading_fees())
    assert fees["BTC/IRT"]["maker"] == D("0.003")
    fee = await call(client.fetch_trading_fee("USDT/IRT"))
    assert fee["taker"] == D("0.0015")
    with pytest.raises(errors.BadSymbol):
        await call(client.fetch_trading_fee("DOGE/IRT"))


async def test_fetch_market_suspensions(client: Any, mock: respx.MockRouter) -> None:
    route(mock, "private_get_mkt_markets_suspensions")
    assert await call(client.fetch_market_suspensions()) == {"BTC/IRT": False, "ETH/USDT": True}


async def test_describe_and_has(client: Any) -> None:
    info = client.describe()
    assert info["id"] == "bitpin"
    assert info["has"]["fetchOHLCV"] is True
    assert info["has"]["editOrder"] is False
    assert "30m" in info["timeframes"]
    assert info["rateLimits"]["auth"] == "3/min"
    assert client.has["createOrder"] is True


@pytest.mark.parametrize("limit", [0, -1])
async def test_fetch_ohlcv_rejects_non_positive_limit(client: Any, limit: int) -> None:
    with pytest.raises(errors.BadRequest, match="limit"):
        await call(client.fetch_ohlcv("BTC/IRT", "1h", limit=limit))
