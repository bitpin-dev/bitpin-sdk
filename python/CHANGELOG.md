# Changelog

All notable changes to the Python SDK. From 0.1.0 on, this file is maintained by release-please from Conventional Commits.

## [0.1.0](https://github.com/bitpin-dev/bitpin-sdk/releases/tag/python-v0.1.0) (2026-10-27)

First release of the official Bitpin SDK for Python. / اولین نسخهٔ SDK رسمی بیت‌پین برای پایتون.

### Features

* Sync `Bitpin` and async `AsyncBitpin` clients with identical methods, ccxt names and ccxt result structures; every number is `Decimal`.
* Market data: markets, currencies, networks, tickers, order book, recent trades, candles (11 timeframes), trading fees, market suspensions.
* Trading: limit, market, stop-limit and OCO orders with local validation; bulk create and cancel (10 per request); cancel by id or client order id; open/closed orders; fills; paginated order history.
* Wallet: balances, bank accounts, deposit addresses, currency networks, deposits, withdrawals (crypto, IRT, internal transfer) with OTP verification.
* WebSocket (`[ws]` extra): `watch_ticker`, `watch_ohlcv`, `watch_order_book`, `watch_trades`, `watch_orders`, `watch_my_trades`.
* Automatic token caching and refresh, with a shareable `FileTokenStore` for the 3-per-minute authenticate limit.
* Client-side rate limiting with the server's default buckets, overridable per bucket for VIP limits.
* Retries only for idempotent requests; orders, cancels and withdrawals are never retried.
* ccxt-compatible exception hierarchy; features Bitpin doesn't offer yet raise `NotSupported` in English and Persian.
* Implicit methods for every `/api/` endpoint in `spec/bitpin.yaml`.
* Documentation in English and Persian, `llms.txt`, dry-run examples including a market-maker skeleton.
