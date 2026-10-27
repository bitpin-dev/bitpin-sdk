# Go

`github.com/bitpin-dev/bitpin-sdk/go`, package `bitpin`. It's the same SDK in Go, with the same behaviour as Python and TypeScript. Every call takes a `context.Context`, returns `(T, error)`, and is safe to use from many goroutines.

```bash
go get github.com/bitpin-dev/bitpin-sdk/go
```

```go
client, err := bitpin.New(bitpin.ConfigFromEnv()) // BITPIN_API_KEY, BITPIN_SECRET_KEY, BITPIN_DOMAIN
if err != nil {
	log.Fatal(err)
}
ticker, err := client.FetchTicker(ctx, "BTC/IRT")
order, err := client.CreateOrder(ctx, "USDT/IRT", "limit", "buy", "10", "90000", bitpin.Params{"clientOrderId": "bot-1"})
if errors.Is(err, bitpin.ErrInsufficientFunds) {
	// ...
}
err = client.CancelOrderByIdentifier(ctx, "bot-1")
```

## Supported versions

- **Go 1.26 or newer** (`go 1.26.0` in `go.mod`; the newest `centrifuge-go` needs it).
- `go.mod` also pins `toolchain go1.27.3`. With the default `GOTOOLCHAIN=auto`, `go` downloads that exact toolchain, the way uv does for Python. Where `proxy.golang.org` is blocked (it returns 403 from Iran), set `GOTOOLCHAIN=local` and use a local Go 1.26 or newer.
- Releases are tags `go/vX.Y.Z`; `go get github.com/bitpin-dev/bitpin-sdk/go@latest` picks the newest.

## Differences from Python

| | Python | Go |
|---|---|---|
| Calls | `client.fetch_order_book("BTC/IRT")` | `client.FetchOrderBook(ctx, "BTC/IRT", 0)` returns `(OrderBook, error)` |
| Optional arguments | keyword arguments | `0` / `""` / `nil` for "not set", or option structs: `FetchOrdersOptions`, `OrderHistoryOptions`, `TransactionsOptions` |
| Results | dicts with ccxt keys | structs with ccxt fields (`Order.ClientOrderID`, `Order.Filled`); the raw response is in `Info` |
| Numbers | `Decimal` | `decimal.Decimal` from shopspring (alias `bitpin.Decimal`); nullable fields are `*Decimal`. Inputs take `Decimal`, string or number |
| Errors | exception classes | `errors.Is(err, bitpin.ErrInvalidOrder)` follows the ccxt hierarchy; `errors.As(err, &e)` with `*bitpin.Error` gives `Status`, `Body`, `RetryAfter`, `Code`, `Feature` |
| Bulk cancel | `cancel_orders(ids=[...])` | `CancelOrders(ctx, ids, nil)` or `CancelOrders(ctx, nil, identifiers)` |
| Timeouts, cancellation | `timeout` | `Config.Timeout` and the `ctx` you pass |
| WebSocket | `AsyncBitpin` | built in; `Watch*` blocks until the next update or until `ctx` ends |

## Methods

- Markets: `LoadMarkets`, `Market`, `FetchMarkets`, `FetchCurrencies`, `FetchNetworks`, `FetchMarketSuspensions`, `Has`, `RateLimits`, `Config`
- Prices: `FetchTicker`, `FetchTickers`, `FetchOrderBook`, `FetchTrades`, `FetchOHLCV`
- Fees: `FetchTradingFees`, `FetchTradingFee`
- Orders: `CreateOrder`, `CreateOrders`, `FetchOrder`, `FetchOrders`, `FetchOpenOrders`, `FetchClosedOrders`, `FetchOrderHistory`, `CancelOrder`, `CancelOrderByIdentifier`, `CancelOrders`, `FetchMyTrades`
- Wallet: `FetchBalance`, `FetchBankAccounts`, `FetchDepositAddress`, `FetchCurrencyNetworks`, `FetchDeposits`, `FetchWithdrawals`, `Withdraw`, `VerifyWithdrawOTP`, `ResendWithdrawOTP`
- WebSocket: `WatchTicker`, `WatchOHLCV`, `WatchOrderBook`, `WatchTrades`, `WatchOrders`, `WatchMyTrades`, and `Close` to disconnect
- Low level: `Request(ctx, endpointID, pathParams, params, body)`, and `String`, which hides your keys
- Not offered by Bitpin yet (return an error matching `bitpin.ErrNotSupported`): `CancelAllOrders`, `EditOrder`, `FetchAccounts`, `FetchLedger`, `Transfer`, `FetchDepositWithdrawFees`, `FetchPositions`, `SetLeverage`, `CreateDepositAddress`, `WatchBalance`, `WatchTickers`, `SetSandboxMode`

Arguments, limits and results are the same as on the [market data](market-data.md), [trading](trading.md), [wallet](wallet.md) and [WebSocket](websocket.md) pages.

## Configuration

```go
client, err := bitpin.New(bitpin.Config{
	APIKey:     "...",
	SecretKey:  "...",
	Domain:     bitpin.DomainIR,                // DomainOrg (default), DomainIR or DomainMarket
	Timeout:    10 * time.Second,
	MaxRetries: bitpin.Int(3),                  // idempotent requests only
	RateLimits: map[string]string{"orderbook": "10800/min"},
	TokenStore: bitpin.FileTokenStore{},        // share tokens across processes
})
```

## Examples

```bash
go run github.com/bitpin-dev/bitpin-sdk/go/examples/quickstart@latest -symbol BTC/IRT
go run github.com/bitpin-dev/bitpin-sdk/go/examples/marketmaker@latest -symbol USDT/IRT -size 10   # dry-run; add -live
```
