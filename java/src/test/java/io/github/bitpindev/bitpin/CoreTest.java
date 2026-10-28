package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.TestSupport.makeJwt;
import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.DisabledOnOs;
import org.junit.jupiter.api.condition.OS;
import org.junit.jupiter.api.io.TempDir;

class CoreTest {
  @Test
  void formatsDecimals() {
    Object[][] cases = {
      {new BigDecimal("1E-8"), "0.00000001"},
      {0.1, "0.1"},
      {1e-7, "0.0000001"},
      {100, "100"},
      {new BigDecimal("1E+3"), "1000"},
      {"63.0", "63"},
      {"0.000", "0"},
      {"-1.50", "-1.5"},
      {3145737420L, "3145737420"},
      {0.5f, "0.5"},
      {new BigInteger("12345678901234567890"), "12345678901234567890"},
      {(short) 7, "7"},
      {(byte) 8, "8"},
    };
    for (Object[] c : cases) {
      assertEquals(c[1], Numbers.format(c[0]), String.valueOf(c[0]));
    }
    for (Object bad : new Object[] {"abc", true, null, new Object()}) {
      assertThrows(IllegalArgumentException.class, () -> Numbers.format(bad));
    }
    assertNull(Numbers.dec("junk"));
    assertNull(Numbers.dec(""));
    assertNull(Numbers.toDecimal(null));
  }

  @Test
  void symbols() {
    for (String s : List.of("BTC/IRT", "btc/irt", "BTC_IRT", "btc_irt", " BTC/IRT ")) {
      assertEquals("BTC_IRT", Symbols.marketId(s));
    }
    assertEquals("1INCH_USDT", Symbols.marketId("1INCH/USDT"));
    for (String bad :
        new String[] {"BTCIRT", "BTC-IRT", "BTC/", "/IRT", "BTC/IRT/X", "", "BTC_I RT", null}) {
      assertThrows(BadSymbolException.class, () -> Symbols.marketId(bad), String.valueOf(bad));
    }
    assertEquals("BTC/IRT", Symbols.symbol("BTC_IRT"));
    assertThrows(BadSymbolException.class, () -> Symbols.symbol("BTCIRT"));
    assertThrows(BadSymbolException.class, () -> Symbols.symbol(null));
    assertEquals("weird", Symbols.symbolOrRaw("weird"));
    assertEquals("", Symbols.symbolOrRaw(5));
  }

  @Test
  void limiter() {
    double[] now = {1000};
    RateLimiter l = new RateLimiter(Map.of("auth", new RateLimit(3, "min")), () -> now[0]);
    for (double step : new double[] {0, 10, 20}) {
      now[0] = 1000 + step;
      assertEquals(0, l.reserve(List.of("auth")));
    }
    now[0] = 1030;
    assertEquals(30, l.reserve(List.of("auth")));
    RateLimiter burst = new RateLimiter(Map.of("a", new RateLimit(2, "sec")), () -> 1000);
    double[] waits = new double[8];
    for (int i = 0; i < 8; i++) {
      waits[i] = burst.reserve(List.of("a"));
    }
    assertEquals(
        List.of(0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0),
        java.util.Arrays.stream(waits).boxed().toList());
    RateLimiter multi =
        new RateLimiter(
            Map.of("a", new RateLimit(1, "sec"), "b", new RateLimit(1, "min")), () -> 1000);
    assertEquals(0, multi.reserve(List.of("a", "b", "x")));
    assertEquals(60, multi.reserve(List.of("a", "b")));
    double[] t = {0};
    RateLimiter pruned = new RateLimiter(Map.of("a", new RateLimit(2, "sec")), () -> t[0]);
    pruned.reserve(List.of("a"));
    pruned.reserve(List.of("a"));
    t[0] += 5;
    assertEquals(0, pruned.reserve(List.of("a")));
  }

  @Test
  void configAndDomains() {
    Config c = Config.builder().build();
    assertEquals(Domain.ORG, c.domain());
    assertEquals("https://api.bitpin.org", c.restUrl());
    assertEquals("wss://centrifugo.bitpin.org/connection/websocket", c.wsUrl());
    assertEquals(new RateLimit(3, "min"), c.rateLimits().get("auth"));
    for (Domain d : Domain.values()) {
      Config dc = Config.builder().domain(d).build();
      assertEquals("https://api.bitpin." + d.key(), dc.restUrl());
      assertEquals("wss://centrifugo.bitpin." + d.key() + "/connection/websocket", dc.wsUrl());
    }
    Config custom =
        Config.builder().domain(Domain.IR).restUrl("https://proxy.example").wsUrl("").build();
    assertEquals("https://proxy.example", custom.restUrl());
    assertEquals("wss://centrifugo.bitpin.ir/connection/websocket", custom.wsUrl());
    assertEquals("wss://ws.example", Config.builder().wsUrl("wss://ws.example").build().wsUrl());
    IllegalArgumentException bad =
        assertThrows(IllegalArgumentException.class, () -> Domain.parse("com"));
    assertEquals("unknown domain \"com\"; use one of: ir, market, org", bad.getMessage());
    assertEquals(Domain.IR, Domain.parse(" IR "));
    assertEquals(Domain.ORG, Domain.parse(""));

    Config over = Config.builder().rateLimit("orderbook", "10800/min").maxRetries(0).build();
    assertEquals(new RateLimit(10800, "min"), over.rateLimits().get("orderbook"));
    assertEquals(new RateLimit(60, "min"), over.rateLimits().get("matches"));
    assertEquals(0, over.maxRetries());
    assertThrows(
        IllegalArgumentException.class, () -> Config.builder().rateLimit("orderbok", "1/min"));
    assertThrows(
        IllegalArgumentException.class, () -> Config.builder().rateLimit("orderbook", "x"));
    assertThrows(IllegalArgumentException.class, () -> Config.builder().maxRetries(-1));
    assertThrows(
        IllegalArgumentException.class, () -> Config.builder().timeout(java.time.Duration.ZERO));
    assertThrows(NullPointerException.class, () -> Config.builder().timeout(null));
    for (String s : new String[] {"10/minute", "x/min", "0/min", "10", null, "99999999999/min"}) {
      assertThrows(IllegalArgumentException.class, () -> RateLimit.parse(s), s);
    }
    assertThrows(IllegalArgumentException.class, () -> new RateLimit(0, "min"));
    assertThrows(IllegalArgumentException.class, () -> new RateLimit(1, "week"));
    assertEquals(1, new RateLimit(1, "sec").periodSeconds());
    assertEquals(86400, new RateLimit(1, "day").periodSeconds());
    assertEquals("60/min", RateLimit.parse("60/min").toString());
    assertEquals("custom/1", Config.builder().userAgent("custom/1").build().userAgent());

    String text =
        Config.builder().apiKey("AKEY").secretKey("SKEY").build() + " " + Config.builder().build();
    assertFalse(text.contains("AKEY") || text.contains("SKEY"), text);
    assertTrue(text.contains("***"), text);
    Config env = Config.fromEnv().build(); // whatever the environment holds; must not throw
    assertTrue(env.toString().startsWith("Config{"));
  }

  @Test
  void tokens() {
    assertEquals(1234, TokenState.jwtExp(makeJwt(1234)));
    Base64.Encoder enc = Base64.getUrlEncoder().withoutPadding();
    java.util.function.Function<String, String> b =
        s -> "e30." + enc.encodeToString(s.getBytes(StandardCharsets.UTF_8)) + ".sig";
    for (String bad :
        new String[] {
          "not-a-jwt",
          "a.!!!.c",
          b.apply("{\"no\":1}"),
          b.apply("{\"exp\":\"soon\"}"),
          b.apply("[1]"),
          b.apply("{\"exp\":1e999}"),
          null
        }) {
      assertNull(TokenState.jwtExp(bad), bad);
    }
    double[] now = {1_000_000};
    TokenState s = new TokenState(() -> now[0]);
    assertEquals(TokenState.Action.AUTHENTICATE, s.action());
    s.setTokens(makeJwt(now[0] + 900), makeJwt(now[0] + 86400));
    assertEquals(TokenState.Action.OK, s.action());
    now[0] += 900 - 121;
    assertEquals(TokenState.Action.OK, s.action());
    now[0]++;
    assertEquals(TokenState.Action.REFRESH, s.action());
    String old = s.tokens.access();
    s.setAccess(makeJwt(now[0] + 1800));
    s.expireAccess(old);
    assertEquals(TokenState.Action.OK, s.action());
    s.expireAccess(s.tokens.access());
    assertEquals(TokenState.Action.REFRESH, s.action());
    now[0] = 1_000_000 + 86400;
    assertEquals(TokenState.Action.AUTHENTICATE, s.action());
    TokenState opaque = new TokenState(() -> 5);
    assertEquals(new Tokens("a", "r", 905, 5 + 2592000), opaque.setTokens("a", "r"));
    new TokenState(() -> 5).expireAccess("x"); // no tokens yet: nothing to expire
    String text = new Tokens("ACCESS-SECRET", "REFRESH-SECRET", 1, 2).toString();
    assertFalse(text.contains("SECRET"), text);
  }

  @Test
  void errorMapping() {
    record Case(String id, int status, Object body, Class<? extends BitpinException> want) {}
    List<Case> cases =
        List.of(
            new Case(
                "private_get_wlt_wallets", 401, map("detail", "x"), AuthenticationException.class),
            new Case(
                "credentials_post_usr_authenticate",
                406,
                map("detail", "api_credential_wrong"),
                AuthenticationException.class),
            new Case("private_post_wlt_address", 403, null, PermissionDeniedException.class),
            new Case("private_get_odr_orders_id", 404, null, OrderNotFoundException.class),
            new Case("public_get_mth_orderbook_symbol", 404, null, BadRequestException.class),
            new Case(
                "private_post_odr_orders",
                406,
                map("detail", "insufficent_balance"),
                InsufficientFundsException.class),
            new Case(
                "private_delete_odr_orders_id",
                406,
                map("code", "cancel_order_not_allowed"),
                InvalidOrderException.class),
            new Case(
                "private_post_wlt_withdraws_verify_otp_id",
                400,
                map("code", "extra_try"),
                InvalidOtpException.class),
            new Case(
                "private_post_odr_orders",
                400,
                map("price", List.of("required")),
                InvalidOrderException.class),
            new Case("private_get_wlt_networks", 406, map("detail", "x"), ExchangeException.class),
            new Case("public_get_mkt_tickers", 503, "<html>", ExchangeNotAvailableException.class),
            new Case("public_get_mkt_tickers", 418, null, ExchangeException.class));
    for (Case c : cases) {
      BitpinException e = Errors.map(c.id, c.status, c.body, null);
      assertEquals(c.want, e.getClass(), c.toString());
      assertEquals(c.status, e.status());
      assertEquals(c.id, e.endpointId());
    }
    assertInstanceOf(
        BadRequestException.class, Errors.map("x", 400, map("code", "invalid_otp"), ""));
    assertFalse(Errors.map("x", 503, null, "") instanceof ExchangeException);
    assertEquals(
        86398,
        Errors.map("x", 429, map("detail", "Expected available in 86398 seconds."), "")
            .retryAfter()
            .getAsDouble());
    assertEquals(12, Errors.map("x", 429, null, "12").retryAfter().getAsDouble());
    assertTrue(Errors.map("x", 429, null, "soon").retryAfter().isEmpty());
    assertTrue(Errors.map("x", 429, null, "-3").retryAfter().isEmpty());
    assertEquals(
        "extra_try",
        Errors.map("private_post_wlt_withdraws_verify_otp_id", 400, map("code", "extra_try"), "")
            .code());
    assertNull(
        Errors.map("private_post_wlt_withdraws_verify_otp_id", 400, map("code", "invalid"), "")
            .code());
    assertEquals(
        "406 private_post_odr_orders: insufficent_balance",
        Errors.map("private_post_odr_orders", 406, map("detail", "insufficent_balance"), "")
            .getMessage());
    assertEquals("500 x", Errors.map("x", 500, null, "").getMessage());
    assertEquals(
        "418 x: ".length() + 200, Errors.map("x", 418, "a".repeat(300), "").getMessage().length());
    assertEquals("418 x: {\"a\":1}", Errors.map("x", 418, map("a", 1), "").getMessage());
    NotSupportedException ns = Errors.notSupported("editOrder");
    assertTrue(ns.getMessage().contains("ویرایش"), ns.getMessage());
    assertEquals("editOrder", ns.feature());
    assertEquals("InvalidOrder", new InvalidOrderException("x").ccxtName());
    assertEquals("BitpinError", new BitpinException("x").ccxtName());
    for (ErrorRule rule : Spec.ERROR_RULES) {
      assertTrue(Errors.known(rule.error()), rule.error());
    }
    Map<Class<?>, String> names =
        Map.ofEntries(
            Map.entry(ExchangeException.class, "ExchangeError"),
            Map.entry(AuthenticationException.class, "AuthenticationError"),
            Map.entry(PermissionDeniedException.class, "PermissionDenied"),
            Map.entry(InsufficientFundsException.class, "InsufficientFunds"),
            Map.entry(OrderNotFoundException.class, "OrderNotFound"),
            Map.entry(BadRequestException.class, "BadRequest"),
            Map.entry(BadSymbolException.class, "BadSymbol"),
            Map.entry(InvalidOtpException.class, "InvalidOTP"),
            Map.entry(NetworkException.class, "NetworkError"),
            Map.entry(RateLimitExceededException.class, "RateLimitExceeded"),
            Map.entry(RequestTimeoutException.class, "RequestTimeout"),
            Map.entry(ExchangeNotAvailableException.class, "ExchangeNotAvailable"));
    names.forEach(
        (cls, name) -> {
          try {
            BitpinException e =
                (BitpinException)
                    cls.getConstructor(String.class, Throwable.class).newInstance("m", null);
            assertEquals(name, e.ccxtName());
          } catch (ReflectiveOperationException ex) {
            throw new AssertionError(ex);
          }
        });
  }

  @Test
  void buildsRequests() {
    Config cfg = Config.builder().restUrl("https://api.bitpin.org/").build();
    Map<String, Object> params =
        map(
            "symbol",
            "BTC_IRT",
            "state",
            List.of("active", "initial"),
            "limit",
            50,
            "side",
            null,
            "flag",
            true,
            "x",
            List.of(1, "b"),
            "d",
            1.5);
    Requests.Built req = Requests.build(cfg, "private_get_odr_orders", null, params, null);
    assertEquals(
        "https://api.bitpin.org/api/v1/odr/orders/?d=1.5&flag=true&limit=50&state=active%2Cinitial&symbol=BTC_IRT&x=1%2Cb",
        req.url());
    assertNull(req.body());
    Map<String, Object> body =
        map(
            "base_amount",
            new BigDecimal("1E-8"),
            "price",
            3100000000L,
            "stop_price",
            null,
            "f",
            false,
            "n",
            List.of(map("a", 0.1)),
            "list",
            List.of("x"));
    Object sent =
        Json.parse(Requests.build(cfg, "private_post_odr_orders", null, null, body).body());
    assertEquals(
        map(
            "base_amount",
            "0.00000001",
            "price",
            "3100000000",
            "f",
            false,
            "n",
            List.of(map("a", "0.1")),
            "list",
            List.of("x")),
        sent);
    Requests.Built path =
        Requests.build(
            cfg,
            "private_delete_odr_orders_identifier_identifier",
            Map.of("identifier", "a b/c"),
            null,
            null);
    assertEquals("https://api.bitpin.org/api/v1/odr/orders/identifier/a%20b%2Fc/", path.url());
    IllegalArgumentException missing =
        assertThrows(
            IllegalArgumentException.class,
            () -> Requests.build(cfg, "public_get_mth_orderbook_symbol", null, null, null));
    assertTrue(missing.getMessage().contains("missing path parameter \"symbol\""));
    assertThrows(
        IllegalArgumentException.class, () -> Requests.build(cfg, "nope", null, null, null));
    assertEquals(
        "https://api.bitpin.org/api/v1/mkt/tickers/",
        Requests.build(cfg, "public_get_mkt_tickers", null, map("a", null), null).url());
  }

  @Test
  void keyIdMatchesTheOtherLanguages() {
    // Same PBKDF2 derivation as Python, TypeScript and Go: their bots share token files.
    assertEquals("f605d686dd6cec66", TokenStore.keyId("test-key"));
    String id = TokenStore.keyId("MY-API-KEY");
    assertEquals(16, id.length());
    assertEquals(id, TokenStore.keyId("MY-API-KEY"));
    assertNotEquals(id, TokenStore.keyId("other"));
  }

  @Test
  void memoryTokenStore() {
    Tokens tok = new Tokens("a", "r", 100, 200);
    MemoryTokenStore mem = new MemoryTokenStore();
    assertEquals(Optional.empty(), mem.load("k"));
    mem.save("k", tok);
    assertEquals(Optional.of(tok), mem.load("k"));
    mem.clear("k");
    assertEquals(Optional.empty(), mem.load("k"));
  }

  @Test
  void fileTokenStore(@TempDir Path tmp) throws Exception {
    Tokens tok = new Tokens("a", "r", 100, 200);
    Path dir = tmp.resolve("cache");
    FileTokenStore fs = new FileTokenStore(dir);
    assertEquals(dir, fs.dir());
    fs.save("abc", tok);
    fs.save("abc", tok); // replaces
    assertEquals(Optional.of(tok), new FileTokenStore(dir).load("abc"));
    try (var entries = Files.list(dir)) {
      assertEquals(1, entries.count(), "no temp files left behind");
    }
    fs.clear("abc");
    fs.clear("abc");
    assertEquals(Optional.empty(), fs.load("abc"));
    Files.writeString(dir.resolve("bad.json"), "{not json");
    assertEquals(Optional.empty(), fs.load("bad"));
    Files.writeString(dir.resolve("half.json"), "{\"access\":\"a\"}");
    assertEquals(Optional.empty(), fs.load("half"));
    // Python writes snake_case expiry keys
    Files.writeString(
        dir.resolve("py.json"),
        "{\"access\":\"a\",\"refresh\":\"r\",\"access_exp\":100,\"refresh_exp\":200}");
    assertEquals(Optional.of(tok), fs.load("py"));
    Files.writeString(
        dir.resolve("odd.json"), "{\"access\":\"a\",\"refresh\":\"r\",\"accessExp\":\"x\"}");
    assertEquals(Optional.of(new Tokens("a", "r", 0, 0)), fs.load("odd"));
    for (String bad : new String[] {"../x", null, ""}) {
      assertThrows(IllegalArgumentException.class, () -> fs.save(bad, tok));
      assertThrows(IllegalArgumentException.class, () -> fs.load(bad));
      assertThrows(IllegalArgumentException.class, () -> fs.clear(bad));
    }
    Files.createDirectory(dir.resolve("taken.json"));
    Files.writeString(dir.resolve("taken.json").resolve("x"), "x");
    assertThrows(java.io.UncheckedIOException.class, () -> fs.save("taken", tok));
    assertThrows(java.io.UncheckedIOException.class, () -> fs.clear("taken"));
    assertTrue(FileTokenStore.defaultDir().endsWith("bitpin-sdk"));
    assertTrue(new FileTokenStore().dir().endsWith("bitpin-sdk"));
  }

  @Test
  @DisabledOnOs(OS.WINDOWS)
  void fileTokenStoreIsPrivate(@TempDir Path tmp) throws Exception {
    Path dir = tmp.resolve("cache");
    new FileTokenStore(dir).save("abc", new Tokens("a", "r", 1, 2));
    assertEquals(
        "rw-------",
        PosixFilePermissions.toString(Files.getPosixFilePermissions(dir.resolve("abc.json"))));
    assertEquals("rwx------", PosixFilePermissions.toString(Files.getPosixFilePermissions(dir)));
  }

  @Test
  void jsonHelpers() {
    assertEquals("2.5", Json.str(new BigDecimal("2.5")));
    assertEquals("true", Json.str(true));
    assertEquals("", Json.str(null));
    assertEquals(Map.of(), Json.asMap("x"));
    assertEquals(List.of(), Json.asList("x"));
    assertThrows(IllegalArgumentException.class, () -> Json.parse("{"));
    assertThrows(IllegalArgumentException.class, () -> Json.parse(new byte[] {'{'}));
    Object parsed =
        Json.parse("{\"p\":3145737420.10,\"n\":12,\"big\":123456789012345678901234567890}");
    Map<String, Object> m = Json.asMap(parsed);
    assertEquals(new BigDecimal("3145737420.10"), m.get("p"));
    assertEquals(12, m.get("n"));
    assertInstanceOf(BigInteger.class, m.get("big"));
    AtomicReference<String> ref = new AtomicReference<>(Json.write(map("a", List.of(1, "b"))));
    assertEquals("{\"a\":[1,\"b\"]}", ref.get());
  }

  @Test
  void restResponseHeadersIgnoreCase() {
    RestTransport.Response r =
        new RestTransport.Response(200, Map.of("retry-after", "3"), new byte[0]);
    assertEquals("3", r.header("Retry-After"));
    assertNull(r.header("X"));
  }
}
