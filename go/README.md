# bitpin-sdk (Go)

The official Go SDK for the [Bitpin](https://bitpin.ir) exchange API. It uses ccxt method and field names, `decimal.Decimal` numbers, a context on every call, and is safe for concurrent use. It also has automatic token refresh, client-side rate limiting with overridable VIP limits, and WebSocket streams.

SDK رسمی Go برای API صرافی بیت‌پین. [مستندات فارسی](https://bitpin-dev.github.io/bitpin-sdk/fa/go/)

```bash
go get github.com/bitpin-dev/bitpin-sdk/go   # Go 1.26+
```

```go
client, err := bitpin.New(bitpin.ConfigFromEnv()) // BITPIN_API_KEY, BITPIN_SECRET_KEY, BITPIN_DOMAIN
ticker, err := client.FetchTicker(ctx, "BTC/IRT")
order, err := client.CreateOrder(ctx, "USDT/IRT", "limit", "buy", "10", "90000", bitpin.Params{"clientOrderId": "bot-1"})
```

Bitpin has no sandbox, so every call is real. Read the [Go guide](https://bitpin-dev.github.io/bitpin-sdk/go/) and the [full docs](https://bitpin-dev.github.io/bitpin-sdk/).
