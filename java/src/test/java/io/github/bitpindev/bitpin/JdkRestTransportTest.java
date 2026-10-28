package io.github.bitpindev.bitpin;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** The default HTTP layer against a real local server. */
class JdkRestTransportTest {
  private HttpServer server;
  private String base;
  private final AtomicReference<String> seen = new AtomicReference<>();

  @BeforeEach
  void start() throws IOException {
    server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/api/v1/mkt/tickers/",
        ex -> {
          seen.set(ex.getRequestMethod() + " " + ex.getRequestHeaders().getFirst("User-Agent"));
          byte[] body =
              "[{\"symbol\":\"BTC_IRT\",\"price\":\"3145737420.10\"}]"
                  .getBytes(StandardCharsets.UTF_8);
          ex.getResponseHeaders().add("Retry-After", "7");
          ex.sendResponseHeaders(200, body.length);
          try (OutputStream out = ex.getResponseBody()) {
            out.write(body);
          }
        });
    server.createContext(
        "/api/v1/odr/orders/",
        ex -> {
          String body = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
          seen.set(
              ex.getRequestMethod()
                  + " "
                  + ex.getRequestHeaders().getFirst("Content-Type")
                  + " "
                  + body);
          ex.sendResponseHeaders(406, -1);
          ex.close();
        });
    server.createContext(
        "/api/v1/mth/matches/",
        ex -> {
          try {
            Thread.sleep(2000);
          } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
          }
          ex.sendResponseHeaders(200, -1);
          ex.close();
        });
    server.start();
    base = "http://127.0.0.1:" + server.getAddress().getPort();
  }

  @AfterEach
  void stop() {
    server.stop(0);
  }

  @Test
  void sendsAndParses() {
    Bitpin c = new Bitpin(Config.builder().restUrl(base).build());
    Ticker t = c.fetchTicker("BTC/IRT");
    assertEquals("3145737420.10", t.last().toPlainString());
    assertTrue(seen.get().startsWith("GET bitpin-sdk-java/"), seen.get());
  }

  @Test
  void mapsErrorStatuses() {
    Bitpin c = new Bitpin(Config.builder().restUrl(base).apiKey("k").secretKey("s").build());
    BitpinException rejected =
        assertThrows(
            BitpinException.class,
            () ->
                c.request("credentials_post_usr_authenticate", null, null, Map.of("api_key", "k")));
    assertEquals(404, rejected.status());
  }

  @Test
  void timesOut() {
    Bitpin c =
        new Bitpin(
            Config.builder().restUrl(base).timeout(Duration.ofMillis(200)).maxRetries(0).build());
    RequestTimeoutException e =
        assertThrows(RequestTimeoutException.class, () -> c.fetchTrades("BTC/IRT"));
    assertTrue(e.getMessage().contains("timed out"));
  }

  @Test
  void headersArePassedThrough() throws Exception {
    JdkRestTransport t = new JdkRestTransport(java.net.http.HttpClient.newHttpClient());
    RestTransport.Response r =
        t.send(
            new RestTransport.Request(
                "GET",
                java.net.URI.create(base + "/api/v1/mkt/tickers/"),
                Map.of("User-Agent", "probe"),
                null,
                Duration.ofSeconds(2)));
    assertEquals(200, r.status());
    assertEquals("7", r.header("Retry-After"));
    assertEquals("GET probe", seen.get());
    RestTransport.Response post =
        t.send(
            new RestTransport.Request(
                "POST",
                java.net.URI.create(base + "/api/v1/odr/orders/"),
                Map.of("Content-Type", "application/json"),
                "{\"a\":\"1\"}",
                Duration.ofSeconds(2)));
    assertEquals(406, post.status());
    assertEquals("POST application/json {\"a\":\"1\"}", seen.get());
    assertNull(post.header("Retry-After"));
  }
}
