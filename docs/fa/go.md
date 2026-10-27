# Go

`github.com/bitpin-dev/bitpin-sdk/go` با پکیج `bitpin`: همان SDK به زبان Go، با همان رفتار پایتون و تایپ‌اسکریپت. هر فراخوانی یک `context.Context` می‌گیرد، `(T, error)` برمی‌گرداند و استفادهٔ هم‌زمان از چند goroutine امن است.

```bash
go get github.com/bitpin-dev/bitpin-sdk/go
```

```go
client, err := bitpin.New(bitpin.ConfigFromEnv()) // BITPIN_API_KEY، BITPIN_SECRET_KEY، BITPIN_DOMAIN
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

## نسخه‌های پشتیبانی‌شده

- **Go نسخهٔ ۱٫۲۶ یا بالاتر** (`go 1.26.0` در `go.mod`؛ آخرین نسخهٔ `centrifuge-go` آن را لازم دارد).
- `go.mod` همچنین `toolchain go1.27.3` را مشخص می‌کند. با تنظیم پیش‌فرض `GOTOOLCHAIN=auto`، دستور `go` دقیقاً همان toolchain را دانلود می‌کند؛ مثل کاری که uv برای پایتون می‌کند. جایی که `proxy.golang.org` مسدود است (از ایران خطای 403 می‌دهد)، `GOTOOLCHAIN=local` را تنظیم کنید و از Go نسخهٔ ۱٫۲۶ یا بالاتر روی سیستم خودتان استفاده کنید.
- نسخه‌ها با تگ `go/vX.Y.Z` منتشر می‌شوند؛ `go get github.com/bitpin-dev/bitpin-sdk/go@latest` جدیدترین را می‌گیرد.

## تفاوت با پایتون

| | پایتون | Go |
|---|---|---|
| فراخوانی | `client.fetch_order_book("BTC/IRT")` | `client.FetchOrderBook(ctx, "BTC/IRT", 0)` که `(OrderBook, error)` برمی‌گرداند |
| آرگومان‌های اختیاری | آرگومان‌های کلیدی | `0` / `""` / `nil` یعنی «تنظیم نشده»، یا ساختارهای گزینه: `FetchOrdersOptions`، `OrderHistoryOptions`، `TransactionsOptions` |
| خروجی | دیکشنری با کلیدهای ccxt | struct با فیلدهای ccxt (`Order.ClientOrderID`، `Order.Filled`)؛ پاسخ خام در `Info` است |
| اعداد | `Decimal` | `decimal.Decimal` از shopspring (نام دیگر: `bitpin.Decimal`)؛ فیلدهای اختیاری `*Decimal` هستند. ورودی‌ها `Decimal`، رشته یا عدد می‌پذیرند |
| خطاها | کلاس‌های استثنا | `errors.Is(err, bitpin.ErrInvalidOrder)` سلسله‌مراتب ccxt را دنبال می‌کند؛ `errors.As(err, &e)` با `*bitpin.Error` فیلدهای `Status`، `Body`، `RetryAfter`، `Code` و `Feature` را می‌دهد |
| لغو گروهی | `cancel_orders(ids=[...])` | `CancelOrders(ctx, ids, nil)` یا `CancelOrders(ctx, nil, identifiers)` |
| مهلت و لغو درخواست | `timeout` | `Config.Timeout` و همان `ctx` که می‌دهید |
| وب‌سوکت | `AsyncBitpin` | داخلی؛ `Watch*` تا به‌روزرسانی بعدی یا پایان `ctx` منتظر می‌ماند |

## متدها

- بازارها: `LoadMarkets`، `Market`، `FetchMarkets`، `FetchCurrencies`، `FetchNetworks`، `FetchMarketSuspensions`، `Has`، `RateLimits`، `Config`
- قیمت‌ها: `FetchTicker`، `FetchTickers`، `FetchOrderBook`، `FetchTrades`، `FetchOHLCV`
- کارمزد: `FetchTradingFees`، `FetchTradingFee`
- سفارش‌ها: `CreateOrder`، `CreateOrders`، `FetchOrder`، `FetchOrders`، `FetchOpenOrders`، `FetchClosedOrders`، `FetchOrderHistory`، `CancelOrder`، `CancelOrderByIdentifier`، `CancelOrders`، `FetchMyTrades`
- کیف پول: `FetchBalance`، `FetchBankAccounts`، `FetchDepositAddress`، `FetchCurrencyNetworks`، `FetchDeposits`، `FetchWithdrawals`، `Withdraw`، `VerifyWithdrawOTP`، `ResendWithdrawOTP`
- وب‌سوکت: `WatchTicker`، `WatchOHLCV`، `WatchOrderBook`، `WatchTrades`، `WatchOrders`، `WatchMyTrades` و `Close` برای قطع اتصال
- سطح پایین: `Request(ctx, endpointID, pathParams, params, body)` و `String` که کلیدهای شما را پنهان می‌کند
- فعلاً در بیت‌پین موجود نیست (خطایی برمی‌گردانند که با `bitpin.ErrNotSupported` جور است): `CancelAllOrders`، `EditOrder`، `FetchAccounts`، `FetchLedger`، `Transfer`، `FetchDepositWithdrawFees`، `FetchPositions`، `SetLeverage`، `CreateDepositAddress`، `WatchBalance`، `WatchTickers`، `SetSandboxMode`

آرگومان‌ها، محدودیت‌ها و خروجی‌ها همان‌هایی است که در صفحه‌های [داده‌های بازار](market-data.md)، [معامله](trading.md)، [کیف پول](wallet.md) و [وب‌سوکت](websocket.md) آمده است.

## پیکربندی

```go
client, err := bitpin.New(bitpin.Config{
	APIKey:     "...",
	SecretKey:  "...",
	Domain:     bitpin.DomainIR,                // DomainOrg (پیش‌فرض)، DomainIR یا DomainMarket
	Timeout:    10 * time.Second,
	MaxRetries: bitpin.Int(3),                  // فقط برای درخواست‌های تکرارپذیر
	RateLimits: map[string]string{"orderbook": "10800/min"},
	TokenStore: bitpin.FileTokenStore{},        // اشتراک توکن بین پروسه‌ها
})
```

## مثال‌ها

```bash
go run github.com/bitpin-dev/bitpin-sdk/go/examples/quickstart@latest -symbol BTC/IRT
go run github.com/bitpin-dev/bitpin-sdk/go/examples/marketmaker@latest -symbol USDT/IRT -size 10   # آزمایشی؛ برای اجرای واقعی -live اضافه کنید
```
