# Bitpin SDK

The official SDK for the [Bitpin](https://bitpin.ir) exchange API. It is built for market makers, VIP traders and the AI agents that write their bots.

- **Python, sync and async.** `Bitpin` and `AsyncBitpin` have the same methods. Go and TypeScript are planned.
- **ccxt-shaped.** Method names and result structures follow [ccxt](https://github.com/ccxt/ccxt), so a ccxt bot ports with small changes. See [Migrating from ccxt](migrating-from-ccxt.md).
- **Exact numbers.** Prices and amounts are `decimal.Decimal`; nothing passes through float.
- **Safe defaults.** Tokens are cached and refreshed automatically, the client stays under Bitpin's rate limits, and only idempotent requests are retried. Orders and withdrawals are never retried.
- **Honest about gaps.** Features Bitpin doesn't offer yet raise `NotSupported` with a clear message. See [Not available yet](not-supported.md).

```bash
pip install bitpin-sdk          # REST
pip install "bitpin-sdk[ws]"    # + WebSocket streams
```

```python
from bitpin_sdk import Bitpin

with Bitpin({"apiKey": "...", "secret": "..."}) as client:
    print(client.fetch_ticker("BTC/IRT")["last"])
    order = client.create_order("USDT/IRT", "limit", "buy", "10", "90000")
    client.cancel_order(order["id"])
```

Next: [Quickstart](quickstart.md).

!!! warning "No sandbox"
    Bitpin has no testnet. Every call reaches the real exchange with real money. The examples print what they would send unless you pass `--live`.
