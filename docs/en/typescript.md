# TypeScript

`bitpin-sdk` on npm: the same SDK for TypeScript and JavaScript, with ccxt JS names and the same behaviour as the Python SDK. Node 22 or newer; Bun and Deno work too. It's meant for servers and bots: API secrets don't belong in a browser.

```bash
npm install bitpin-sdk
```

```ts
import { Bitpin, InsufficientFunds } from "bitpin-sdk";

const client = new Bitpin({ apiKey: process.env.BITPIN_API_KEY, secret: process.env.BITPIN_SECRET_KEY });
const ticker = await client.fetchTicker("BTC/IRT");
console.log(ticker.last?.toString());

const order = await client.createOrder("USDT/IRT", "limit", "buy", "10", "90000", { clientOrderId: "bot-1" });
await client.cancelOrderByIdentifier("bot-1");
```

Without options, `new Bitpin()` reads `BITPIN_API_KEY` and `BITPIN_SECRET_KEY` from the environment.

## Differences from Python

| | Python | TypeScript |
|---|---|---|
| Clients | `Bitpin` (sync) and `AsyncBitpin` | one `Bitpin`; every method returns a `Promise` |
| Names | `fetch_order_book` | `fetchOrderBook` (ccxt JS) |
| Implicit API | `client.public_get_mkt_tickers()` | `client.publicGetMktTickers()` |
| Numbers | `decimal.Decimal` | `Decimal` from decimal.js, re-exported: `import { Decimal } from "bitpin-sdk"` |
| `timeout` | seconds | milliseconds, as in ccxt JS |
| Bulk cancel | `cancel_orders(ids=[...])` | `cancelOrders({ ids: [...] })` or `{ identifiers: [...] }` |
| Token store | `FileTokenStore()` | `new FileTokenStore()` (Node), async `TokenStore` interface |
| WebSocket | `AsyncBitpin` only | built in |

## Methods

- Markets: `loadMarkets`, `market`, `fetchMarkets`, `fetchCurrencies`, `fetchNetworks`, `fetchMarketSuspensions`, `describe`
- Prices: `fetchTicker`, `fetchTickers`, `fetchOrderBook`, `fetchTrades`, `fetchOHLCV` (alias `fetchOhlcv`)
- Fees: `fetchTradingFees`, `fetchTradingFee`
- Orders: `createOrder`, `createOrders`, `fetchOrder`, `fetchOrders`, `fetchOpenOrders`, `fetchClosedOrders`, `fetchOrderHistory`, `cancelOrder`, `cancelOrderByIdentifier`, `cancelOrders`, `fetchMyTrades`
- Wallet: `fetchBalance`, `fetchBankAccounts`, `fetchDepositAddress`, `fetchCurrencyNetworks`, `fetchDeposits`, `fetchWithdrawals`, `withdraw`, `verifyWithdrawOtp`, `resendWithdrawOtp`
- WebSocket: `watchTicker`, `watchOHLCV`, `watchOrderBook`, `watchTrades`, `watchOrders`, `watchMyTrades`, and `close` to disconnect
- Low level: `request(endpointId, pathParams, params, body)`
- Not offered by Bitpin yet (they throw `NotSupported`): `cancelAllOrders`, `editOrder`, `fetchAccounts`, `fetchLedger`, `transfer`, `fetchDepositWithdrawFees`, `fetchPositions`, `setLeverage`, `createDepositAddress`, `watchBalance`, `watchTickers`, `setSandboxMode`

Arguments, limits and results are the same as on the [market data](market-data.md), [trading](trading.md), [wallet](wallet.md) and [WebSocket](websocket.md) pages.

## Configuration

```ts
const client = new Bitpin({
  apiKey: "...",
  secretKey: "...",            // or `secret`, as in ccxt
  timeout: 10_000,             // ms
  maxRetries: 3,               // idempotent requests only
  rateLimits: { orderbook: "10800/min" },
  tokenStore: new FileTokenStore(),
});
```

## Errors

The classes are the same as in Python and ccxt, and are exported both directly and as `errors`:

```ts
import { errors, InsufficientFunds } from "bitpin-sdk";

try {
  await client.createOrder("USDT/IRT", "limit", "buy", "10", "90000");
} catch (error) {
  if (error instanceof InsufficientFunds) { /* ... */ }
  if (error instanceof errors.RateLimitExceeded) console.log(error.retryAfter);
}
```

## Examples

`examples/ts/` has `quickstart.ts`, `place-and-cancel.ts` and `market-maker.ts`. They print the requests they would send unless you pass `--live`.

```bash
node --experimental-strip-types examples/ts/quickstart.ts --symbol BTC/IRT
```
