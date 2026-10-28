# جاوا

`io.github.bitpin-dev:bitpin-sdk` با پکیج `io.github.bitpindev.bitpin`: همان SDK به زبان جاوا، با همان رفتار پایتون، تایپ‌اسکریپت و Go. هر متد تا رسیدن پاسخ منتظر می‌ماند (blocking) و یک کلاینت `Bitpin` را می‌توان بین چند thread به اشتراک گذاشت؛ برای اجرای هم‌زمان چند فراخوانی از virtual thread استفاده کنید.

=== "Maven"

    ```xml
    <dependency>
      <groupId>io.github.bitpin-dev</groupId>
      <artifactId>bitpin-sdk</artifactId>
      <version>0.1.0</version>
    </dependency>
    ```

=== "Gradle"

    ```kotlin
    implementation("io.github.bitpin-dev:bitpin-sdk:0.1.0")
    ```

```java
import io.github.bitpindev.bitpin.*;
import java.math.BigDecimal;
import java.util.Map;

try (Bitpin client = new Bitpin(Config.fromEnv().build())) { // BITPIN_API_KEY، BITPIN_SECRET_KEY، BITPIN_DOMAIN
  Ticker ticker = client.fetchTicker("BTC/IRT");
  Order order = client.createOrder("USDT/IRT", "limit", "buy",
      new BigDecimal("10"), new BigDecimal("90000"), Map.of("clientOrderId", "bot-1"));
  client.cancelOrderByIdentifier("bot-1");
} catch (InsufficientFundsException e) {
  // ...
}
```

## نسخه‌های پشتیبانی‌شده

- **جاوا ۲۱ یا بالاتر** (فایل jar برای جاوا ۲۱ ساخته می‌شود و CI روی ۲۱، ۲۵ و ۲۷ آزمایش می‌کند). مخزن برای توسعه JDK 25 را در `java/.java-version` مشخص می‌کند، مثل `.python-version` در پایتون، و با Maven wrapper (`./mvnw`، Maven 3.10.0) ساخته می‌شود؛ لازم نیست خودتان Maven نصب کنید.
- وابستگی‌های زمان اجرا: Jackson 3 برای JSON (پکیج‌های `tools.jackson` آن با Jackson 2 در برنامهٔ شما تداخل ندارند) و کلاینت رسمی Centrifugo یعنی `centrifuge-java` برای وب‌سوکت، روی okhttp 5.
- نسخه‌ها با تگ `java-vX.Y.Z` منتشر می‌شوند و در Maven Central قرار می‌گیرند.

## تفاوت با پایتون

| | پایتون | جاوا |
|---|---|---|
| فراخوانی | `client.fetch_order_book("BTC/IRT")` | `client.fetchOrderBook("BTC/IRT")` که `OrderBook` برمی‌گرداند؛ blocking و thread-safe |
| آرگومان‌های اختیاری | آرگومان‌های کلیدی | overloadها، و `null` یعنی «تنظیم نشده»: `fetchOrders(symbol, since, limit, params)` |
| خروجی | دیکشنری با کلیدهای ccxt | record با نام‌های ccxt (`order.clientOrderId()`، `order.filled()`)؛ پاسخ خام در `info()` است |
| اعداد | `Decimal` | همه‌جا `BigDecimal`، هم ورودی و هم خروجی؛ مقدار ناموجود `null` است |
| خطاها | کلاس‌های استثنا | استثناهای unchecked با سلسله‌مراتب ccxt و نام‌گذاری جاوا: `InsufficientFundsException` از `ExchangeException` و آن از `BitpinException` ارث می‌برد. `status()`، `body()`، `retryAfter()`، `code()`، `feature()` و `ccxtName()` جزئیات را می‌دهند |
| لغو گروهی | `cancel_orders(ids=[...])` | `cancelOrders(ids, null)` یا `cancelOrders(null, identifiers)` |
| مهلت | `timeout` | `Config.builder().timeout(Duration)`؛ هر `watch*` هم یک مهلت `Duration` می‌پذیرد |
| وب‌سوکت | هر دو کلاینت | داخلی؛ `watch*` تا به‌روزرسانی بعدی منتظر می‌ماند |

## متدها

- بازارها: `loadMarkets`، `market`، `fetchMarkets`، `fetchCurrencies`، `fetchNetworks`، `fetchMarketSuspensions`، `has`، `rateLimits`، `config`
- قیمت‌ها: `fetchTicker`، `fetchTickers`، `fetchOrderBook`، `fetchTrades`، `fetchOHLCV`
- کارمزد: `fetchTradingFees`، `fetchTradingFee`
- سفارش‌ها: `createOrder`، `createOrders`، `fetchOrder`، `fetchOrders`، `fetchOpenOrders`، `fetchClosedOrders`، `fetchOrderHistory`، `cancelOrder`، `cancelOrderByIdentifier`، `cancelOrders`، `fetchMyTrades`
- کیف پول: `fetchBalance`، `fetchBankAccounts`، `fetchDepositAddress`، `fetchCurrencyNetworks`، `fetchDeposits`، `fetchWithdrawals`، `withdraw`، `verifyWithdrawOtp`، `resendWithdrawOtp`
- وب‌سوکت: `watchTicker`، `watchOHLCV`، `watchOrderBook`، `watchTrades`، `watchOrders`، `watchMyTrades` و `close` برای قطع اتصال (`Bitpin` از `AutoCloseable` پیروی می‌کند)
- سطح پایین: `request(endpointId, pathParams, params, body)` و `toString` که کلیدهای شما را پنهان می‌کند
- فعلاً در بیت‌پین موجود نیست (`NotSupportedException` پرتاب می‌کنند): `cancelAllOrders`، `editOrder`، `fetchAccounts`، `fetchLedger`، `transfer`، `fetchDepositWithdrawFees`، `fetchPositions`، `setLeverage`، `createDepositAddress`، `watchBalance`، `watchTickers`، `setSandboxMode`

آرگومان‌ها، محدودیت‌ها و خروجی‌ها همان‌هایی است که در صفحه‌های [داده‌های بازار](market-data.md)، [معامله](trading.md)، [کیف پول](wallet.md) و [وب‌سوکت](websocket.md) آمده است.

## پیکربندی

```java
Config config = Config.builder()
    .apiKey("...").secretKey("...")
    .domain(Domain.IR)                       // ORG (پیش‌فرض)، IR یا MARKET
    .timeout(Duration.ofSeconds(10))
    .maxRetries(3)                           // فقط برای درخواست‌های تکرارپذیر
    .rateLimit("orderbook", "10800/min")
    .tokenStore(new FileTokenStore())        // اشتراک توکن بین پروسه‌ها
    .build();
```

با `httpClient(HttpClient)` کلاینت HTTP جاوای خودتان را می‌دهید (پروکسی، تنظیمات TLS)؛ `restTransport(...)` کل لایهٔ HTTP را جایگزین می‌کند.

## چند بازار هم‌زمان

```java
try (var pool = Executors.newVirtualThreadPerTaskExecutor()) {
  for (String symbol : List.of("BTC/IRT", "USDT/IRT", "ETH/USDT")) {
    pool.submit(() -> {
      while (true) {
        OrderBook book = client.watchOrderBook(symbol);
        // قیمت‌دهی ...
      }
    });
  }
}
```

کلاینت همهٔ فراخوانی‌ها را، از هر threadی که باشند، زیر محدودیت نرخ بیت‌پین نگه می‌دارد.

## مثال‌ها

از پوشهٔ `java/` در نسخهٔ clone‌شدهٔ مخزن:

```bash
./mvnw -q compile dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
java -cp "target/classes:$(cat target/classpath.txt)" examples/Quickstart.java BTC/IRT
java -cp "target/classes:$(cat target/classpath.txt)" examples/MarketMaker.java --symbol USDT/IRT --size 10   # آزمایشی؛ برای اجرای واقعی --live اضافه کنید
```
