---
name: bitpin-trading-bot
description: Write a trading bot, market-making loop, strategy or script that trades on Bitpin with the bitpin-sdk Python package. Use when a user asks an agent to automate trading, quoting, order management or withdrawals on Bitpin.
---

# Write a Bitpin trading bot

You are writing software that moves a user's real money on an exchange with no sandbox. Build it to be **safe by default**.

## Before writing code

1. Read `llms.txt` (or `llms-full.txt`) from the bitpin-sdk repository for the API surface.
2. Ask the user for what you can't assume: markets, order sizes, spreads or strategy parameters, maximum position or loss, and whether they have VIP rate limits (then they go in `Config(rate_limits=...)`).

## Shape of the bot

- **Dry-run first.** The bot takes `--live`. Without it, it reads real market data but prints the orders it would place. Start every run in dry-run.
- **Config from the environment.** `Config.from_env()`; keys never appear in code, logs or committed files. Several processes on one host share tokens with `FileTokenStore()`.
- **Know the market.** `load_markets()` once; round prices down (bids) or up (asks) to `market["precision"]["price"]` and amounts to `["amount"]`, using `Decimal`.
- **Own your orders.** Every order carries `params={"clientOrderId": ...}` with a unique, recognisable prefix. Cancel by identifier; on startup, find and cancel stale orders with that prefix (`fetch_open_orders`).
- **Reconcile, don't assume.** After a `NetworkError` on `create_order`, the order may exist: look it up by `clientOrderId` before placing again. Cancels are asynchronous: confirm with `fetch_order` or `watch_orders`.
- **State from REST, changes from WebSocket.** Read the book and open orders with REST, then follow `watch_order_book` / `watch_orders` (async client). Fall back to polling if the stream drops.
- **Limits.** Batch with `create_orders` / `cancel_orders` (10 per request). Handle `RateLimitExceeded` by waiting `retry_after`. Handle `InsufficientFunds` by skipping the round, not by retrying.
- **Kill switch.** On Ctrl-C, an unhandled error or a breached loss limit, cancel the bot's open orders before exiting.
- **Withdrawals** only when the user explicitly asks; they need the user's OTP codes, typed at runtime.

## Done when

- `--live` is required for any write, and dry-run output shows every order it would send.
- Prices and amounts are rounded to the market's precision with `Decimal`.
- Every order has a `clientOrderId`, and shutdown cancels the bot's open orders.
- The user has run it in dry-run and read the output before going live.

`examples/python/market_maker.py` in the repository is a minimal starting point that follows these rules.
