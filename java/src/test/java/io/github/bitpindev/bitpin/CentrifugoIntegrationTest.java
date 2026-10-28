package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;

import io.github.bitpindev.bitpin.TestSupport.MockHttp;
import io.github.bitpindev.bitpin.TestSupport.Reply;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * The real Centrifugo client (centrifuge-java on okhttp) against a real Centrifugo server: a public
 * channel without a token, and a user channel with a token from ws-info. CI starts the server;
 * locally: {@code CENTRIFUGO_URL=http://127.0.0.1:18000 mvn test -Dgroups=centrifugo}.
 */
@Tag("centrifugo")
class CentrifugoIntegrationTest {
  private static final String BASE = env("CENTRIFUGO_URL", "http://127.0.0.1:18000");
  private static final String API_KEY = env("CENTRIFUGO_API_KEY", "test-api");
  private static final String HMAC = env("CENTRIFUGO_HMAC", "test-hmac");
  private static final HttpClient HTTP = HttpClient.newHttpClient();

  private static String env(String name, String fallback) {
    String v = System.getenv(name);
    return v == null || v.isEmpty() ? fallback : v;
  }

  private static String wsUrl() {
    return BASE.replaceFirst("^http", "ws") + "/connection/websocket";
  }

  static String token(String user) throws Exception {
    Base64.Encoder b = Base64.getUrlEncoder().withoutPadding();
    String head =
        b.encodeToString("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
    long exp = System.currentTimeMillis() / 1000 + 600;
    String body =
        b.encodeToString(
            ("{\"sub\":\"" + user + "\",\"exp\":" + exp + "}").getBytes(StandardCharsets.UTF_8));
    Mac mac = Mac.getInstance("HmacSHA256");
    mac.init(new SecretKeySpec(HMAC.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
    String sig =
        b.encodeToString(mac.doFinal((head + "." + body).getBytes(StandardCharsets.UTF_8)));
    return head + "." + body + "." + sig;
  }

  static void publish(String channel, Map<String, Object> data) throws Exception {
    HttpRequest req =
        HttpRequest.newBuilder(URI.create(BASE + "/api/publish"))
            .header("X-API-Key", API_KEY)
            .header("Content-Type", "application/json")
            .POST(
                HttpRequest.BodyPublishers.ofString(
                    Json.write(map("channel", channel, "data", data))))
            .build();
    HTTP.send(req, HttpResponse.BodyHandlers.discarding());
  }

  /** Publishes until the watcher gets it: subscribing is asynchronous. */
  static <T> T until(CompletableFuture<T> watcher, String channel, Map<String, Object> data)
      throws Exception {
    for (int i = 0; i < 100 && !watcher.isDone(); i++) {
      publish(channel, data);
      Thread.sleep(100);
    }
    return watcher.get(5, TimeUnit.SECONDS);
  }

  static <T> CompletableFuture<T> async(java.util.concurrent.Callable<T> fn) {
    return WebSocketTest.async(fn);
  }

  @Test
  void publicChannelWithoutToken() throws Exception {
    try (Bitpin client = new Bitpin(Config.builder().wsUrl(wsUrl()).build())) {
      CompletableFuture<Ticker> next =
          async(() -> client.watchTicker("BTC/IRT", Duration.ofSeconds(15)));
      Ticker t = until(next, "market:BTC_IRT", WebSocketTest.WS_TICKER);
      assertEquals("BTC/IRT", t.symbol());
      assertEquals("3145737420", t.last().toPlainString());
    }
  }

  @Test
  void userChannelWithToken() throws Exception {
    MockHttp http = new MockHttp();
    http.endpoint("credentials_post_usr_authenticate");
    http.endpoint(
        "credentials_post_usr_ws_info",
        Reply.of(200, map("ws_token", token("TESTUSR1"), "user_identifier", "TESTUSR1")));
    Config cfg =
        Config.builder().apiKey("k").secretKey("s").restTransport(http).wsUrl(wsUrl()).build();
    try (Bitpin client = new Bitpin(cfg)) {
      CompletableFuture<Order> next =
          async(() -> client.watchOrders("BTC/IRT", Duration.ofSeconds(15)));
      Map<String, Object> order =
          new java.util.LinkedHashMap<>(Json.asMap(Fixtures.body("private_post_odr_orders")));
      order.put("event", "user_order_update");
      Order o = until(next, "user:order_info#TESTUSR1", order);
      assertEquals("535179385", o.id());
    }
  }
}
