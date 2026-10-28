# Java

`io.github.bitpin-dev:bitpin-sdk`, package `io.github.bitpindev.bitpin`. It's the same SDK in Java, with the same behaviour as Python, TypeScript and Go. Every method blocks until the answer arrives, and one `Bitpin` client is safe to share between threads; run many calls at once on virtual threads.

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

try (Bitpin client = new Bitpin(Config.fromEnv().build())) { // BITPIN_API_KEY, BITPIN_SECRET_KEY, BITPIN_DOMAIN
  Ticker ticker = client.fetchTicker("BTC/IRT");
  Order order = client.createOrder("USDT/IRT", "limit", "buy",
      new BigDecimal("10"), new BigDecimal("90000"), Map.of("clientOrderId", "bot-1"));
  client.cancelOrderByIdentifier("bot-1");
} catch (InsufficientFundsException e) {
  // ...
}
```

## Supported versions

- **Java 21 or newer** (the jar targets Java 21; CI tests 21, 25 and 27). The repository pins JDK 25 in `java/.java-version` for development, the way `.python-version` does for Python, and builds with the Maven wrapper (`./mvnw`, Maven 3.10.0); you don't install Maven yourself.
- Runtime dependencies: Jackson 3 for JSON (its `tools.jackson` packages don't clash with Jackson 2 in your app), and Centrifugo's official client `centrifuge-java` for the WebSocket, on okhttp 5.
- Releases are tags `java-vX.Y.Z` and go to Maven Central.

## Differences from Python

| | Python | Java |
|---|---|---|
| Calls | `client.fetch_order_book("BTC/IRT")` | `client.fetchOrderBook("BTC/IRT")` returns `OrderBook`; blocking, thread-safe |
| Optional arguments | keyword arguments | overloads, and `null` for "not set": `fetchOrders(symbol, since, limit, params)` |
| Results | dicts with ccxt keys | records with ccxt names (`order.clientOrderId()`, `order.filled()`); the raw response is `info()` |
| Numbers | `Decimal` | `BigDecimal` everywhere, in and out; absent values are `null` |
| Errors | exception classes | unchecked exceptions in the ccxt hierarchy with Java names: `InsufficientFundsException` extends `ExchangeException` extends `BitpinException`. `status()`, `body()`, `retryAfter()`, `code()`, `feature()` and `ccxtName()` give the details |
| Bulk cancel | `cancel_orders(ids=[...])` | `cancelOrders(ids, null)` or `cancelOrders(null, identifiers)` |
| Timeouts | `timeout` | `Config.builder().timeout(Duration)`; every `watch*` also takes a `Duration` timeout |
| WebSocket | both clients | built in; `watch*` blocks until the next update |

## Methods

- Markets: `loadMarkets`, `market`, `fetchMarkets`, `fetchCurrencies`, `fetchNetworks`, `fetchMarketSuspensions`, `has`, `rateLimits`, `config`
- Prices: `fetchTicker`, `fetchTickers`, `fetchOrderBook`, `fetchTrades`, `fetchOHLCV`
- Fees: `fetchTradingFees`, `fetchTradingFee`
- Orders: `createOrder`, `createOrders`, `fetchOrder`, `fetchOrders`, `fetchOpenOrders`, `fetchClosedOrders`, `fetchOrderHistory`, `cancelOrder`, `cancelOrderByIdentifier`, `cancelOrders`, `fetchMyTrades`
- Wallet: `fetchBalance`, `fetchBankAccounts`, `fetchDepositAddress`, `fetchCurrencyNetworks`, `fetchDeposits`, `fetchWithdrawals`, `withdraw`, `verifyWithdrawOtp`, `resendWithdrawOtp`
- WebSocket: `watchTicker`, `watchOHLCV`, `watchOrderBook`, `watchTrades`, `watchOrders`, `watchMyTrades`, and `close` to disconnect (`Bitpin` is `AutoCloseable`)
- Low level: `request(endpointId, pathParams, params, body)`, and `toString`, which hides your keys
- Not offered by Bitpin yet (throw `NotSupportedException`): `cancelAllOrders`, `editOrder`, `fetchAccounts`, `fetchLedger`, `transfer`, `fetchDepositWithdrawFees`, `fetchPositions`, `setLeverage`, `createDepositAddress`, `watchBalance`, `watchTickers`, `setSandboxMode`

Arguments, limits and results are the same as on the [market data](market-data.md), [trading](trading.md), [wallet](wallet.md) and [WebSocket](websocket.md) pages.

## Configuration

```java
Config config = Config.builder()
    .apiKey("...").secretKey("...")
    .domain(Domain.IR)                       // ORG (default), IR or MARKET
    .timeout(Duration.ofSeconds(10))
    .maxRetries(3)                           // idempotent requests only
    .rateLimit("orderbook", "10800/min")
    .tokenStore(new FileTokenStore())        // share tokens across processes
    .build();
```

`httpClient(HttpClient)` passes your own JDK HTTP client (a proxy, TLS settings); `restTransport(...)` replaces the HTTP layer entirely.

## Many markets at once

```java
try (var pool = Executors.newVirtualThreadPerTaskExecutor()) {
  for (String symbol : List.of("BTC/IRT", "USDT/IRT", "ETH/USDT")) {
    pool.submit(() -> {
      while (true) {
        OrderBook book = client.watchOrderBook(symbol);
        // quote ...
      }
    });
  }
}
```

The client keeps every call under Bitpin's rate limits, whichever thread makes it.

## Examples

From `java/` in a clone of the repository:

```bash
./mvnw -q compile dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
java -cp "target/classes:$(cat target/classpath.txt)" examples/Quickstart.java BTC/IRT
java -cp "target/classes:$(cat target/classpath.txt)" examples/MarketMaker.java --symbol USDT/IRT --size 10   # dry-run; add --live
```
