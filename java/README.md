# bitpin-sdk (Java)

The official Java SDK for the [Bitpin](https://bitpin.ir) exchange API. It uses ccxt method and field names, `BigDecimal` numbers and records, blocking thread-safe calls that scale on virtual threads, automatic token refresh, client-side rate limiting with overridable VIP limits, and WebSocket streams through Centrifugo's official Java client.

SDK رسمی جاوا برای API صرافی بیت‌پین. [مستندات فارسی](https://bitpin-dev.github.io/bitpin-sdk/fa/java/)

```xml
<dependency>
  <groupId>io.github.bitpin-dev</groupId>
  <artifactId>bitpin-sdk</artifactId>
  <version>0.1.0</version> <!-- x-release-please-version -->
</dependency>
```

```java
try (Bitpin client = new Bitpin(Config.fromEnv().build())) { // BITPIN_API_KEY, BITPIN_SECRET_KEY, BITPIN_DOMAIN
  Ticker ticker = client.fetchTicker("BTC/IRT");
  Order order = client.createOrder("USDT/IRT", "limit", "buy",
      new BigDecimal("10"), new BigDecimal("90000"), Map.of("clientOrderId", "bot-1"));
}
```

Java 21 or newer. Bitpin has no sandbox, so every call is real. Read the [Java guide](https://bitpin-dev.github.io/bitpin-sdk/java/) and the [full docs](https://bitpin-dev.github.io/bitpin-sdk/).
