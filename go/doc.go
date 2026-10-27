// Package bitpin is the official Go SDK for the Bitpin exchange API.
//
//	client, err := bitpin.New(bitpin.ConfigFromEnv()) // BITPIN_API_KEY, BITPIN_SECRET_KEY, BITPIN_DOMAIN
//	ticker, err := client.FetchTicker(ctx, "BTC/IRT")
//	order, err := client.CreateOrder(ctx, "USDT/IRT", "limit", "buy", "10", "90000", bitpin.Params{"clientOrderId": "bot-1"})
//
// Unified methods use ccxt names and result structures; prices and amounts are
// decimal.Decimal. Every method takes a context.Context and is safe for concurrent use.
// Errors match the ccxt hierarchy through errors.Is: errors.Is(err, bitpin.ErrInvalidOrder).
//
// Bitpin has no sandbox: every call reaches the real exchange.
//
// Docs: https://bitpin-dev.github.io/bitpin-sdk/go/
package bitpin

// Version is the SDK version.
const Version = "0.1.0" // x-release-please-version
