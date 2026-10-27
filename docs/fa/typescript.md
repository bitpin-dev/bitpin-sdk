# تایپ‌اسکریپت

بستهٔ `bitpin-sdk` در npm: همان SDK برای تایپ‌اسکریپت و جاوااسکریپت، با نام‌های ccxt JS و همان رفتار SDK پایتون. به Node نسخهٔ ۲۲ یا بالاتر نیاز دارد؛ Bun و Deno هم کار می‌کنند. برای سرور و ربات ساخته شده است؛ کلید مخفی API نباید در مرورگر باشد.

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

`new Bitpin()` بدون تنظیمات، `BITPIN_API_KEY`، `BITPIN_SECRET_KEY` و `BITPIN_DOMAIN` را از متغیرهای محیطی می‌خواند.

## نسخه‌های پشتیبانی‌شده

- **محیط اجرا:** Node.js نسخهٔ ۲۲ یا بالاتر (`"engines"` در `package.json`)، آزموده‌شده روی Node ۲۲، ۲۴ و ۲۶. Bun و Deno هم کار می‌کنند.
- **تایپ‌ها:** فایل‌های تعریف نوع با TypeScript ۵٫۰ یا بالاتر کار می‌کنند؛ خود SDK با TypeScript ۷ ساخته می‌شود.
- **مشارکت‌کنندگان:** از نسخهٔ Node در `ts/.nvmrc` استفاده کنید (nvm، fnm، mise و Volta آن را می‌خوانند). `devEngines` در `package.json` باعث می‌شود npm با Node قدیمی‌تر از ۲۲ یا npm قدیمی‌تر از ۱۰٫۹ کار نکند.

## تفاوت با پایتون

| | پایتون | تایپ‌اسکریپت |
|---|---|---|
| کلاینت‌ها | `Bitpin` (همگام) و `AsyncBitpin` | یک `Bitpin`؛ همهٔ متدها `Promise` برمی‌گردانند |
| نام‌ها | `fetch_order_book` | `fetchOrderBook` (مثل ccxt JS) |
| API ضمنی | `client.public_get_mkt_tickers()` | `client.publicGetMktTickers()` |
| اعداد | `decimal.Decimal` | `Decimal` از decimal.js که دوباره export شده است: `import { Decimal } from "bitpin-sdk"` |
| `timeout` | ثانیه | میلی‌ثانیه، مثل ccxt JS |
| لغو گروهی | `cancel_orders(ids=[...])` | `cancelOrders({ ids: [...] })` یا `{ identifiers: [...] }` |
| ذخیرهٔ توکن | `FileTokenStore()` | `new FileTokenStore()` (در Node)، رابط ناهمگام `TokenStore` |
| وب‌سوکت | فقط `AsyncBitpin` | داخلی |

## متدها

- بازارها: `loadMarkets`، `market`، `fetchMarkets`، `fetchCurrencies`، `fetchNetworks`، `fetchMarketSuspensions`، `describe`
- قیمت‌ها: `fetchTicker`، `fetchTickers`، `fetchOrderBook`، `fetchTrades`، `fetchOHLCV` (نام دیگر: `fetchOhlcv`)
- کارمزد: `fetchTradingFees`، `fetchTradingFee`
- سفارش‌ها: `createOrder`، `createOrders`، `fetchOrder`، `fetchOrders`، `fetchOpenOrders`، `fetchClosedOrders`، `fetchOrderHistory`، `cancelOrder`، `cancelOrderByIdentifier`، `cancelOrders`، `fetchMyTrades`
- کیف پول: `fetchBalance`، `fetchBankAccounts`، `fetchDepositAddress`، `fetchCurrencyNetworks`، `fetchDeposits`، `fetchWithdrawals`، `withdraw`، `verifyWithdrawOtp`، `resendWithdrawOtp`
- وب‌سوکت: `watchTicker`، `watchOHLCV`، `watchOrderBook`، `watchTrades`، `watchOrders`، `watchMyTrades` و `close` برای قطع اتصال
- سطح پایین: `request(endpointId, pathParams, params, body)`
- فعلاً در بیت‌پین موجود نیست (خطای `NotSupported` می‌دهند): `cancelAllOrders`، `editOrder`، `fetchAccounts`، `fetchLedger`، `transfer`، `fetchDepositWithdrawFees`، `fetchPositions`، `setLeverage`، `createDepositAddress`، `watchBalance`، `watchTickers`، `setSandboxMode`

آرگومان‌ها، محدودیت‌ها و خروجی‌ها همان‌هایی است که در صفحه‌های [داده‌های بازار](market-data.md)، [معامله](trading.md)، [کیف پول](wallet.md) و [وب‌سوکت](websocket.md) آمده است.

## پیکربندی

```ts
const client = new Bitpin({
  apiKey: "...",
  secretKey: "...",            // یا `secret`، مثل ccxt
  domain: "org",               // "org" (پیش‌فرض)، "ir" یا "market"؛ REST و وب‌سوکت با هم عوض می‌شوند
  timeout: 10_000,             // میلی‌ثانیه
  maxRetries: 3,               // فقط برای درخواست‌های تکرارپذیر
  rateLimits: { orderbook: "10800/min" },
  tokenStore: new FileTokenStore(),
});
```

## خطاها

کلاس‌ها همان کلاس‌های پایتون و ccxt هستند و هم مستقیم و هم زیر `errors` export شده‌اند:

```ts
import { errors, InsufficientFunds } from "bitpin-sdk";

try {
  await client.createOrder("USDT/IRT", "limit", "buy", "10", "90000");
} catch (error) {
  if (error instanceof InsufficientFunds) { /* ... */ }
  if (error instanceof errors.RateLimitExceeded) console.log(error.retryAfter);
}
```

## مثال‌ها

در `examples/ts/` فایل‌های `quickstart.ts`، `place-and-cancel.ts` و `market-maker.ts` هست. تا وقتی `--live` ندهید فقط درخواست‌هایی را که می‌فرستند چاپ می‌کنند.

```bash
node --experimental-strip-types examples/ts/quickstart.ts --symbol BTC/IRT
```
