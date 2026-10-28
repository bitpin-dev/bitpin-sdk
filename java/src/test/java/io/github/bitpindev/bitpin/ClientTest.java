package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.TestSupport.TEST_NOW;
import static io.github.bitpindev.bitpin.TestSupport.env;
import static io.github.bitpindev.bitpin.TestSupport.fixtureAccess;
import static io.github.bitpindev.bitpin.TestSupport.makeJwt;
import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.bitpindev.bitpin.TestSupport.Env;
import io.github.bitpindev.bitpin.TestSupport.Reply;
import io.github.bitpindev.bitpin.TestSupport.Route;
import java.io.IOException;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;

class ClientTest {
  @Test
  void sendsHeadersAndAuthenticatesOnce() {
    Env e = env();
    Route tickers = e.http().endpoint("public_get_mkt_tickers");
    e.client().request("public_get_mkt_tickers", null, null, null);
    assertNull(tickers.last().header("Authorization"));
    assertEquals("bitpin-sdk-java/" + Version.VERSION, tickers.last().header("User-Agent"));
    assertEquals("application/json", tickers.last().header("Accept"));
    assertNull(tickers.last().header("Content-Type"));

    Route wallets = e.http().endpoint("private_get_wlt_wallets");
    e.client().request("private_get_wlt_wallets", null, null, null);
    e.client().request("private_get_wlt_wallets", null, null, null);
    assertEquals(1, e.auth().count());
    assertEquals(map("api_key", "test-key", "secret_key", "test-secret"), e.auth().last().body());
    assertEquals("application/json", e.auth().last().header("Content-Type"));
    assertEquals("Bearer " + fixtureAccess(), wallets.last().header("Authorization"));

    Bitpin anon = new Bitpin(Config.builder().restTransport(e.http()).build());
    assertThrows(
        AuthenticationException.class,
        () -> anon.request("private_get_wlt_wallets", null, null, null));
    assertThrows(
        IllegalArgumentException.class, () -> e.client().request("nope", null, null, null));
    assertThrows(NullPointerException.class, () -> new Bitpin(null));
  }

  @Test
  void refreshesThenReauthenticates() {
    Env e = env();
    Route auth =
        e.http()
            .endpoint(
                "credentials_post_usr_authenticate",
                Reply.of(
                    200,
                    map("access", makeJwt(TEST_NOW + 900), "refresh", makeJwt(TEST_NOW + 86400))));
    Route refresh =
        e.http()
            .endpoint(
                "credentials_post_usr_refresh_token",
                Reply.of(200, map("access", makeJwt(TEST_NOW + 1800))));
    Route wallets = e.http().endpoint("private_get_wlt_wallets");
    e.client().request("private_get_wlt_wallets", null, null, null);
    e.time().advance(840);
    e.client().request("private_get_wlt_wallets", null, null, null);
    assertEquals(1, refresh.count());
    assertEquals(map("refresh", makeJwt(TEST_NOW + 86400)), refresh.last().body());
    assertEquals("Bearer " + makeJwt(TEST_NOW + 1800), wallets.last().header("Authorization"));

    e.http()
        .endpoint("credentials_post_usr_refresh_token", Reply.of(401, map("detail", "expired")));
    e.time().advance(1800);
    e.client().request("private_get_wlt_wallets", null, null, null);
    assertEquals(2, auth.count());

    e.http().endpoint("credentials_post_usr_refresh_token", Reply.of(503, null));
    e.time().advance(1800);
    assertThrows(
        ExchangeNotAvailableException.class,
        () -> e.client().request("private_get_wlt_wallets", null, null, null));
  }

  @Test
  void unauthorizedRetriesOnce() {
    Env e = env();
    e.http().endpoint("credentials_post_usr_refresh_token");
    Route w =
        e.http()
            .on(
                "GET",
                "/api/v1/wlt/wallets/",
                Reply.of(401, map("detail", "revoked")),
                Reply.of(200, List.of()));
    e.client().request("private_get_wlt_wallets", null, null, null);
    assertEquals(List.of(2, 1), List.of(w.count(), e.auth().count()));
    e.http().endpoint("private_get_wlt_wallets", Reply.of(401, map("detail", "revoked")));
    assertThrows(
        AuthenticationException.class,
        () -> e.client().request("private_get_wlt_wallets", null, null, null));
    e.http().endpoint("public_get_mkt_tickers", Reply.of(401, null));
    assertThrows(
        AuthenticationException.class,
        () -> e.client().request("public_get_mkt_tickers", null, null, null));
  }

  @Test
  void concurrentCallsAuthenticateOnce() throws Exception {
    Env e = env();
    e.http().endpoint("private_get_wlt_wallets");
    try (ExecutorService pool = Executors.newVirtualThreadPerTaskExecutor()) {
      List<Future<?>> futures = new ArrayList<>();
      for (int i = 0; i < 20; i++) {
        futures.add(
            pool.submit(() -> e.client().request("private_get_wlt_wallets", null, null, null)));
      }
      for (Future<?> f : futures) {
        f.get();
      }
    }
    assertEquals(1, e.auth().count());
  }

  @Test
  void tokenStoreIsShared() {
    MemoryTokenStore store = new MemoryTokenStore();
    Env a = env(b -> b.tokenStore(store));
    a.http().endpoint("private_get_wlt_wallets");
    a.client().request("private_get_wlt_wallets", null, null, null);
    Bitpin b =
        new Bitpin(
            Config.builder()
                .apiKey("test-key")
                .secretKey("test-secret")
                .restTransport(a.http())
                .tokenStore(store)
                .clock(a.time())
                .sleeper(a.time())
                .build());
    b.request("private_get_wlt_wallets", null, null, null);
    assertEquals(1, a.auth().count());

    TokenStore broken =
        new TokenStore() {
          @Override
          public java.util.Optional<Tokens> load(String keyId) {
            throw new IllegalStateException("disk gone");
          }

          @Override
          public void save(String keyId, Tokens tokens) {}

          @Override
          public void clear(String keyId) {}
        };
    Env c = env(x -> x.tokenStore(broken));
    c.http().endpoint("private_get_wlt_wallets");
    c.client().request("private_get_wlt_wallets", null, null, null);
    assertEquals(1, c.auth().count());
  }

  @Test
  void retriesOnlyIdempotentRequests() {
    Env e = env();
    Route tk =
        e.http()
            .on(
                "GET",
                "/api/v1/mkt/tickers/",
                Reply.fail(new IOException("connection reset")),
                Reply.of(200, List.of()));
    e.client().request("public_get_mkt_tickers", null, null, null);
    assertEquals(2, tk.count());
    assertEquals(List.of(0.5), e.time().slept());

    Env few = env(b -> b.maxRetries(2));
    Route down = few.http().endpoint("public_get_mkt_tickers", Reply.of(503, null));
    assertThrows(
        ExchangeNotAvailableException.class,
        () -> few.client().request("public_get_mkt_tickers", null, null, null));
    assertEquals(3, down.count());
    assertEquals(List.of(0.5, 1.0), few.time().slept());

    for (Reply failure :
        List.of(
            Reply.of(429, map("detail", "Expected available in 1 seconds.")),
            Reply.fail(new HttpTimeoutException("timeout")),
            Reply.of(503, null))) {
      Env w = env();
      Route orders = w.http().on("POST", "/api/v1/odr/orders/", failure, Reply.of(201, map()));
      assertThrows(
          NetworkException.class,
          () ->
              w.client().request("private_post_odr_orders", null, null, map("symbol", "BTC_IRT")));
      assertEquals(1, orders.count());
    }

    Env shortWait = env();
    shortWait
        .http()
        .on(
            "GET",
            "/api/v1/mkt/tickers/",
            Reply.of(429, map("detail", "Expected available in 2 seconds.")),
            Reply.of(200, List.of()));
    shortWait.client().request("public_get_mkt_tickers", null, null, null);
    assertEquals(List.of(2.0), shortWait.time().slept());
    shortWait
        .http()
        .endpoint(
            "public_get_mkt_tickers",
            Reply.of(429, map("detail", "Expected available in 86398 seconds.")));
    RateLimitExceededException rl =
        assertThrows(
            RateLimitExceededException.class,
            () -> shortWait.client().request("public_get_mkt_tickers", null, null, null));
    assertEquals(86398, rl.retryAfter().getAsDouble());
    shortWait.http().endpoint("public_get_mkt_tickers", Reply.of(429, null));
    assertThrows(
        RateLimitExceededException.class,
        () -> shortWait.client().request("public_get_mkt_tickers", null, null, null));

    Env none = env(b -> b.maxRetries(0));
    none.http().on("GET", "/api/v1/mkt/tickers/", Reply.fail(new HttpTimeoutException("slow")));
    assertThrows(
        RequestTimeoutException.class,
        () -> none.client().request("public_get_mkt_tickers", null, null, null));
    none.http().on("GET", "/api/v1/mkt/tickers/", Reply.fail(new IOException("down")));
    NetworkException ne =
        assertThrows(
            NetworkException.class,
            () -> none.client().request("public_get_mkt_tickers", null, null, null));
    assertEquals(NetworkException.class, ne.getClass());
    assertNotNull(ne.getCause());
    assertEquals("public_get_mkt_tickers", ne.endpointId());
  }

  @Test
  void limiterSpacesRequests() throws Exception {
    Env e = env(b -> b.rateLimit("tickers", "2/min"));
    e.http().endpoint("public_get_mkt_tickers");
    for (int i = 0; i < 3; i++) {
      e.client().request("public_get_mkt_tickers", null, null, null);
    }
    assertEquals(List.of(60.0), e.time().slept());

    Env off = env(b -> b.rateLimit("tickers", "1/min").disableRateLimit());
    off.http().endpoint("public_get_mkt_tickers");
    for (int i = 0; i < 3; i++) {
      off.client().request("public_get_mkt_tickers", null, null, null);
    }
    assertTrue(off.time().slept().isEmpty());
    assertFalse(off.client().config().rateLimitEnabled());

    List<Double> sleeps = Collections.synchronizedList(new ArrayList<>());
    Env burst =
        env(b -> b.rateLimit("orderbook", "2/sec").sleeper(d -> sleeps.add(d.toNanos() / 1e9)));
    burst.http().endpoint("public_get_mth_orderbook_symbol");
    try (ExecutorService pool = Executors.newVirtualThreadPerTaskExecutor()) {
      List<Future<?>> futures = new ArrayList<>();
      for (int i = 0; i < 8; i++) {
        futures.add(pool.submit(() -> burst.client().fetchOrderBook("BTC/IRT")));
      }
      for (Future<?> f : futures) {
        f.get();
      }
    }
    List<Double> sorted = new ArrayList<>(sleeps);
    Collections.sort(sorted);
    assertEquals(List.of(1.0, 1.0, 2.0, 2.0, 3.0, 3.0), sorted);

    Env interrupted =
        env(
            b ->
                b.rateLimit("tickers", "1/min")
                    .sleeper(
                        d -> {
                          throw new InterruptedException();
                        }));
    interrupted.http().endpoint("public_get_mkt_tickers");
    interrupted.client().request("public_get_mkt_tickers", null, null, null);
    BitpinException ex =
        assertThrows(
            BitpinException.class,
            () -> interrupted.client().request("public_get_mkt_tickers", null, null, null));
    assertInstanceOf(InterruptedException.class, ex.getCause());
    assertTrue(Thread.interrupted()); // the flag is restored (and cleared here)
  }

  @Test
  void responsesAndSecrets() {
    Env e = env(b -> b.maxRetries(0));
    e.http().endpoint("private_delete_odr_orders_id");
    assertNull(e.client().request("private_delete_odr_orders_id", Map.of("id", 1), null, null));

    e.http().on("GET", "/api/v1/mkt/tickers/", Reply.text(502, "<html>bad gateway</html>"));
    BitpinException bad =
        assertThrows(
            BitpinException.class,
            () -> e.client().request("public_get_mkt_tickers", null, null, null));
    assertEquals("<html>bad gateway</html>", bad.body());
    assertEquals(502, bad.status());

    e.http().on("GET", "/api/v1/mkt/tickers/", Reply.text(200, "not json"));
    ExchangeException invalid =
        assertThrows(
            ExchangeException.class,
            () -> e.client().request("public_get_mkt_tickers", null, null, null));
    assertTrue(invalid.getMessage().contains("invalid JSON"));

    Env fresh = env(b -> b.maxRetries(0));
    fresh
        .http()
        .endpoint(
            "credentials_post_usr_authenticate",
            Reply.of(406, map("detail", "api_credential_wrong")));
    AuthenticationException auth =
        assertThrows(
            AuthenticationException.class,
            () -> fresh.client().request("private_get_wlt_wallets", null, null, null));
    String text =
        auth + " " + auth.getMessage() + " " + fresh.client() + " " + fresh.client().config();
    assertFalse(text.contains("test-secret"), text);
    assertFalse(text.contains("test-key"), text);
    assertTrue(text.contains("***"), text);

    fresh.http().on("POST", "/api/v1/usr/authenticate/", Reply.fail(new IOException("down")));
    NetworkException ne =
        assertThrows(
            NetworkException.class,
            () -> fresh.client().request("private_get_wlt_wallets", null, null, null));
    assertNull(ne.getCause(), "credentials errors must not chain the request");
  }

  @Test
  void interruptedTransportRestoresTheFlag() {
    Bitpin c =
        new Bitpin(
            Config.builder()
                .restTransport(
                    r -> {
                      throw new InterruptedException();
                    })
                .build());
    BitpinException e = assertThrows(BitpinException.class, () -> c.fetchTickers());
    assertInstanceOf(InterruptedException.class, e.getCause());
    assertTrue(Thread.interrupted());
  }

  @Test
  void late401DoesNotRefreshAgain() {
    Env e = env();
    String first = fixtureAccess();
    Route refresh =
        e.http()
            .endpoint(
                "credentials_post_usr_refresh_token",
                Reply.of(200, map("access", makeJwt(TEST_NOW + 5000))));
    e.http().endpoint("private_get_wlt_wallets");
    e.client().request("private_get_wlt_wallets", null, null, null);
    TokenState tokens = tokenState(e.client());
    tokens.setAccess(makeJwt(TEST_NOW + 4000));
    tokens.expireAccess(first);
    e.client().request("private_get_wlt_wallets", null, null, null);
    assertEquals(0, refresh.count());
  }

  static TokenState tokenState(Bitpin client) {
    try {
      var f = Bitpin.class.getDeclaredField("tokens");
      f.setAccessible(true);
      return (TokenState) f.get(client);
    } catch (ReflectiveOperationException ex) {
      throw new AssertionError(ex);
    }
  }

  @Test
  void domainReachesTheRequests() {
    Env e = env(b -> b.domain(Domain.MARKET));
    e.http().endpoint("public_get_mkt_tickers");
    e.client().fetchTickers();
    assertEquals("https://api.bitpin.market", e.client().config().restUrl());
    assertEquals(Domain.MARKET, e.client().config().domain());
  }

  @Test
  void defaultsAndIntrospection() {
    try (Bitpin c = new Bitpin()) {
      assertEquals("bitpin", c.id);
      assertEquals("Bitpin", c.name);
      assertEquals(Domain.ORG, c.config().domain());
      assertEquals(new RateLimit(3, "min"), c.rateLimits().get("auth"));
      assertFalse(c.has().get("editOrder"));
      assertTrue(c.has().get("fetchOHLCV"));
      assertEquals(Duration.ofSeconds(10), c.config().timeout());
      assertEquals(3, c.config().maxRetries());
      assertTrue(c.config().userAgent().startsWith("bitpin-sdk-java/"));
    }
  }
}
