package io.github.bitpindev.bitpin;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.net.http.HttpClient;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * Live, read-only checks against the real Bitpin API. Never run in CI.
 *
 * <pre>BITPIN_LIVE=1 [BITPIN_API_KEY=... BITPIN_SECRET_KEY=...] ./mvnw verify -Plive</pre>
 */
@Tag("live")
class LiveTest {
  private static final Set<String> ALLOWED_WRITES =
      Set.of("/api/v1/usr/authenticate/", "/api/v1/usr/refresh_token/", "/api/v1/usr/ws-info/");

  static Bitpin client() {
    assumeTrue("1".equals(System.getenv("BITPIN_LIVE")), "set BITPIN_LIVE=1");
    RestTransport real = new JdkRestTransport(HttpClient.newHttpClient());
    RestTransport readOnly =
        request -> {
          if (!request.method().equals("GET")
              && !ALLOWED_WRITES.contains(request.uri().getPath())) {
            throw new IOException(
                "live tests are read-only: refused "
                    + request.method()
                    + " "
                    + request.uri().getPath());
          }
          return real.send(request);
        };
    return new Bitpin(Config.fromEnv().restTransport(readOnly).maxRetries(1).build());
  }

  /** Every key of the fixture's first row exists live with the same JSON type. */
  static void checkShape(String endpointId, Object live, List<String> problems) {
    Map<String, Object> want = first(Fixtures.body(endpointId));
    Map<String, Object> got = first(live);
    if (want.isEmpty() || got.isEmpty()) {
      return;
    }
    want.forEach(
        (key, value) -> {
          if (!got.containsKey(key)) {
            problems.add(endpointId + ": missing field " + key);
          } else if (value != null && got.get(key) != null && kind(value) != kind(got.get(key))) {
            problems.add(
                endpointId
                    + "."
                    + key
                    + ": type "
                    + kind(got.get(key))
                    + ", fixture "
                    + kind(value));
          }
        });
  }

  private static char kind(Object v) {
    return v instanceof Number
        ? 'n'
        : v instanceof String ? 's' : v instanceof Boolean ? 'b' : v instanceof List ? 'l' : 'm';
  }

  private static Map<String, Object> first(Object v) {
    List<Object> list = Json.asList(v);
    if (!list.isEmpty()) {
      return Json.asMap(list.get(0));
    }
    Map<String, Object> m = Json.asMap(v);
    List<Object> results = Json.asList(m.get("results"));
    return results.isEmpty() ? m : Json.asMap(results.get(0));
  }

  @Test
  void publicEndpoints() {
    Bitpin c = client();
    List<String> problems = new ArrayList<>();
    for (String id :
        List.of(
            "public_get_mkt_currencies",
            "public_get_mkt_markets",
            "public_get_mkt_networks",
            "public_get_mkt_tickers")) {
      checkShape(id, c.request(id, null, null, null), problems);
    }
    checkShape(
        "public_get_mth_orderbook_symbol",
        c.request("public_get_mth_orderbook_symbol", Map.of("symbol", "USDT_IRT"), null, null),
        problems);
    assertTrue(problems.isEmpty(), String.join("\n", problems));
    assertFalse(c.loadMarkets().isEmpty());
    c.fetchTicker("USDT/IRT");
    c.fetchOHLCV("USDT/IRT", "1h", null, 5, null);
  }

  @Test
  void privateReads() {
    Bitpin c = client();
    assumeTrue(
        c.config().toString().contains("apiKey=***"), "set BITPIN_API_KEY and BITPIN_SECRET_KEY");
    List<String> problems = new ArrayList<>();
    for (String id :
        List.of(
            "private_get_mkt_commissions",
            "private_get_odr_orders",
            "private_get_odr_fills",
            "private_get_wlt_wallets",
            "private_get_wlt_deposits",
            "private_get_wlt_withdraws")) {
      checkShape(id, c.request(id, null, Map.of("limit", 5), null), problems);
    }
    assertTrue(problems.isEmpty(), String.join("\n", problems));
    c.fetchBalance();
  }
}
