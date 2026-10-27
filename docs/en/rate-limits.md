# Rate limits

Bitpin limits each endpoint group separately: per user when you send a token, per IP otherwise. The client keeps a sliding window per bucket and waits before a request that would exceed it, so a well-behaved bot doesn't get 429s.

## Defaults

These are the server's default limits. VIP and market-maker accounts often have higher ones. Ask Bitpin for your real limits and set them with `Config(rate_limits=...)` (see [Configuration](configuration.md)).

| Bucket | Default | Used by |
|---|---|---|
| `auth` | 3 / min | authenticate (per IP) |
| `refresh` | 20 / min | token refresh |
| `ws_info` | 10 / min | WebSocket token |
| `market_public` | 200 / min | `fetch_markets`, `fetch_currencies`, `fetch_networks` |
| `market_suspensions` | 2 / min | `fetch_market_suspensions` |
| `tickers` | 300 / min | `fetch_tickers`, `fetch_ticker` |
| `commissions` | 10,000 / day | `fetch_trading_fees`, `fetch_trading_fee` |
| `candles` | 300 / min | `fetch_ohlcv` |
| `orderbook` | 60 / min | `fetch_order_book` |
| `matches` | 60 / min | `fetch_trades` |
| `order_create` | 18,000 / hour | `create_order` |
| `order_read` | 18,000 / hour | `fetch_orders`, `fetch_order`, open/closed orders |
| `order_cancel` | 18,000 / hour | `cancel_order`, `cancel_order_by_identifier` |
| `order_bulk_create` | 1,800 / hour | `create_orders` |
| `order_bulk_cancel` | 1,800 / hour | `cancel_orders`, and also `create_orders` |
| `fills` | 300 / min | `fetch_my_trades` |
| `order_history` | 5 / sec | `fetch_order_history` |
| `wallet` | 60 / min | `fetch_balance`, `fetch_bank_accounts` |
| `deposit_address` | 60 / min | `fetch_deposit_address` |
| `currency_networks` | 60 / min | `fetch_currency_networks` |
| `deposits` | 60 / min | `fetch_deposits` |
| `withdraws` | 60 / min | `fetch_withdrawals`, `withdraw` |
| `withdraw_otp` | 10,000 / day | `verify_withdraw_otp`, `resend_withdraw_otp` |

Bitpin counts a bulk create against the bulk-cancel budget too, and so does the client.

## When the server says 429

The client raises `RateLimitExceeded` with `retry_after` (seconds) when the server gives a hint. An idempotent request (any GET) whose `retry_after` is 5 seconds or less is retried after waiting. Order creation and withdrawals are never retried.

```python
from bitpin_sdk import errors

try:
    client.fetch_order_book("BTC/IRT")
except errors.RateLimitExceeded as exc:
    print("try again in", exc.retry_after, "seconds")
```

## Several processes

The limiter counts per client object. Several processes that use the same key share one server budget, so give each a share, for example `rate_limits={"order_create": "6000/hour"}` for three processes.

Set `enable_rate_limit=False` to turn the client-side limiter off. The server still enforces its limits.
