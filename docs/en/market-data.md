# Market data

Public methods need no API key. Symbols are written `BTC/IRT`; `BTC_IRT` and lower case also work.

| Method | Returns |
|---|---|
| `load_markets(reload=False)` | `{symbol: Market}`, cached on the client |
| `market(symbol)` | one cached `Market` (call `load_markets()` first) |
| `fetch_markets()` | `[Market]` with `precision` (tick sizes) and `active` |
| `fetch_currencies()` | `{code: Currency}` |
| `fetch_networks(params)` | every network; filters `code`, `can_deposit`, `can_withdraw` |
| `fetch_tickers(symbols=None)` | `{symbol: Ticker}` |
| `fetch_ticker(symbol)` | `Ticker`: `last`, `high`, `low`, `percentage` (24h, in %) |
| `fetch_order_book(symbol, limit=None)` | `{"bids": [[price, amount]], "asks": ...}`; 20 levels by default, at most 50 |
| `fetch_trades(symbol, since=None, limit=None)` | recent public trades, oldest first |
| `fetch_ohlcv(symbol, timeframe="30m", since=None, limit=None)` | `[[ms, open, high, low, close, volume]]` |
| `fetch_trading_fees()` / `fetch_trading_fee(symbol)` | your maker/taker fees as ratios (`0.003` = 0.3 %); needs a key |
| `fetch_market_suspensions()` | `{symbol: suspended}` for your account; needs a key, 2 per minute |
| `describe()` | capabilities, timeframes, URLs and effective rate limits |
| `request(endpoint_id, path_params, params=, body=)` | low-level call to any endpoint |

## Candles

Timeframes: `1m 5m 15m 30m 1h 3h 4h 6h 1d 1w 1M` (`1m` is a minute, `1M` a month). Without `since` you get the latest `limit` candles (500 by default). One request returns at most 10,000 candles. An unknown timeframe raises `BadRequest`; the server would silently use `30m`.

## Precision

`market["precision"]["price"]` and `["amount"]` are tick sizes as `Decimal`, for example `Decimal("1")` for IRT prices and `Decimal("1E-8")` for BTC amounts. Round your prices to them before you place orders.

## Implicit API

Every endpoint is also a method named after its id in the spec, taking one dict (path parameters are picked out by name):

```python
client.public_get_mth_orderbook_symbol({"symbol": "BTC_IRT", "limit": 50})
client.private_get_odr_orders({"state": "active"})
```

These return the raw JSON. Prefer the unified methods; use these for fields the unified ones don't expose.
