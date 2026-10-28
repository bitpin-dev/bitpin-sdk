package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.TestSupport.env;
import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

import io.github.bitpindev.bitpin.TestSupport.Env;
import io.github.bitpindev.bitpin.TestSupport.Reply;
import io.github.bitpindev.bitpin.TestSupport.Route;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import java.util.function.UnaryOperator;
import org.junit.jupiter.api.Test;

class WebSocketTest {
  static final class FakeTransport implements WsTransport {
    final String url;
    final TokenSource tokens;
    volatile String token;
    volatile int connects;
    volatile boolean closed;
    volatile RuntimeException failNext;
    private final Map<String, Consumer<byte[]>> handlers = new HashMap<>();

    FakeTransport(String url, TokenSource tokens) {
      this.url = url;
      this.tokens = tokens;
    }

    @Override
    public void connect() {
      connects++;
      if (tokens != null) {
        token = tokens.token();
      }
    }

    @Override
    public synchronized void subscribe(String channel, Consumer<byte[]> onData) {
      if (failNext != null) {
        RuntimeException e = failNext;
        failNext = null;
        throw e;
      }
      handlers.put(channel, onData);
    }

    @Override
    public void close() {
      closed = true;
    }

    synchronized Consumer<byte[]> handler(String channel) {
      return handlers.get(channel);
    }

    void push(String channel, Object data) {
      Consumer<byte[]> h = null;
      for (int i = 0; i < 400 && h == null; i++) {
        h = handler(channel);
        if (h == null) {
          sleep(5);
        }
      }
      if (h == null) {
        fail("no subscription for " + channel);
      }
      h.accept(data instanceof byte[] b ? b : Json.write(data).getBytes(StandardCharsets.UTF_8));
    }
  }

  record WsEnv(Env env, List<FakeTransport> transports, Route info) {
    Bitpin client() {
      return env.client();
    }

    FakeTransport transport() {
      for (int i = 0; i < 400; i++) {
        synchronized (transports) {
          if (!transports.isEmpty()) {
            return transports.get(0);
          }
        }
        sleep(5);
      }
      throw new AssertionError("no transport");
    }
  }

  static void sleep(long ms) {
    try {
      Thread.sleep(ms);
    } catch (InterruptedException e) {
      throw new AssertionError(e);
    }
  }

  @SafeVarargs
  static WsEnv wsEnv(UnaryOperator<Config.Builder>... mutate) {
    List<FakeTransport> transports = new ArrayList<>();
    WsTransport.Factory factory =
        (url, tokens) -> {
          FakeTransport t = new FakeTransport(url, tokens);
          synchronized (transports) {
            transports.add(t);
          }
          return t;
        };
    UnaryOperator<Config.Builder> setup =
        b -> {
          Config.Builder out = b.wsTransport(factory);
          for (UnaryOperator<Config.Builder> m : mutate) {
            out = m.apply(out);
          }
          return out;
        };
    Env e = env(setup);
    Route info = e.http().endpoint("credentials_post_usr_ws_info");
    return new WsEnv(e, transports, info);
  }

  static <T> CompletableFuture<T> async(Callable<T> fn) {
    CompletableFuture<T> f = new CompletableFuture<>();
    Thread.ofVirtual()
        .start(
            () -> {
              try {
                f.complete(fn.call());
              } catch (Throwable t) {
                f.completeExceptionally(t);
              }
            });
    return f;
  }

  static <T> T await(CompletableFuture<T> f) {
    try {
      return f.get(2, TimeUnit.SECONDS);
    } catch (Exception e) {
      throw new AssertionError(e);
    }
  }

  static final Map<String, Object> WS_TICKER =
      map(
          "price",
          "3145737420",
          "change",
          "0.0258",
          "min",
          "3000000000",
          "max",
          "3200000000",
          "mean",
          "3100000000",
          "value",
          "1500000000000",
          "amount",
          "480.5",
          "time",
          "1760873857000",
          "symbol",
          "BTC_IRT",
          "event",
          "currency_price_update");

  @Test
  void watchTicker() {
    WsEnv w = wsEnv();
    CompletableFuture<Ticker> next = async(() -> w.client().watchTicker("BTC/IRT"));
    FakeTransport tr = w.transport();
    tr.push(
        "market:BTC_IRT", map("event", "candle_update", "symbol", "BTC_IRT", "candles", List.of()));
    tr.push("market:BTC_IRT", WS_TICKER);
    Ticker tk = await(next);
    assertEquals(
        List.of("BTC/IRT", "3145737420", "2.58", "480.5"),
        List.of(
            tk.symbol(),
            Numbers.plain(tk.last()),
            Numbers.plain(tk.percentage()),
            Numbers.plain(tk.baseVolume())));
    assertEquals(1760873857000L, tk.timestamp());
    assertEquals("wss://centrifugo.bitpin.org/connection/websocket", tr.url);
    assertEquals(
        Json.str(Json.asMap(Fixtures.body("credentials_post_usr_ws_info")).get("ws_token")),
        tr.token);
    w.client().close();
    assertTrue(tr.closed);
    w.client().close();
  }

  @Test
  void fanOutAndFilters() {
    WsEnv w = wsEnv();
    Map<String, Object> candle =
        map(
            "open",
            "1",
            "close",
            "2",
            "low",
            "0.5",
            "high",
            "3",
            "volume",
            "10",
            "ts",
            "1760873760.0");
    CompletableFuture<List<OHLCV>> one = async(() -> w.client().watchOHLCV("BTC/IRT", "1m"));
    CompletableFuture<List<OHLCV>> five = async(() -> w.client().watchOHLCV("BTC/IRT", "5m"));
    FakeTransport tr = w.transport();
    sleep(30);
    Map<String, Object> c1 = new LinkedHashMap<>(candle);
    c1.put("resolution", "1m");
    Map<String, Object> c5 = new LinkedHashMap<>(candle);
    c5.put("resolution", "5m");
    tr.push("market:BTC_IRT", "not json".getBytes(StandardCharsets.UTF_8));
    tr.push("market:BTC_IRT", "[1]".getBytes(StandardCharsets.UTF_8));
    tr.push("market:BTC_IRT", map("no", "event"));
    tr.push(
        "market:BTC_IRT",
        map("event", "candle_update", "symbol", "BTC_IRT", "candles", List.of(c1, c5)));
    assertEquals(1760873760000L, await(one).get(0).timestamp());
    assertEquals(1, await(five).size());
    assertEquals(1, tr.connects);
    assertThrows(BadRequestException.class, () -> w.client().watchOHLCV("BTC/IRT", "2h"));

    CompletableFuture<OrderBook> book = async(() -> w.client().watchOrderBook("BTC_IRT"));
    tr.push(
        "orderbook:BTC_IRT",
        map(
            "asks",
            List.of(List.of("3160000000", "0.2"), List.of("3150000000", "0.01")),
            "bids",
            List.of(List.of("3130000000", "1"), List.of("3140000000", "0.05")),
            "symbol",
            "BTC_IRT",
            "event_time",
            "2025-10-19T11:38:27.929164Z",
            "event",
            "market_data"));
    OrderBook ob = await(book);
    assertEquals("3140000000", Numbers.plain(ob.bids().get(0).price()));
    assertEquals("3150000000", Numbers.plain(ob.asks().get(0).price()));
    assertEquals(1760873907929L, ob.timestamp());

    CompletableFuture<List<Trade>> trades = async(() -> w.client().watchTrades("BTC/IRT"));
    tr.push(
        "matches:BTC_IRT",
        map(
            "event",
            "matches_update",
            "symbol",
            "BTC_IRT",
            "matches",
            List.of(
                map(
                    "id",
                    "1_2",
                    "price",
                    "1",
                    "base_amount",
                    "2",
                    "quote_amount",
                    "2",
                    "side",
                    "buy",
                    "time",
                    1760873797.149016))));
    Trade got = await(trades).get(0);
    assertEquals("1_2", got.id());
    assertEquals(1760873797149L, got.timestamp());

    List<Runnable> bad =
        List.of(
            () -> w.client().watchTicker("bad"),
            () -> w.client().watchOHLCV("bad", "1m"),
            () -> w.client().watchOrderBook("bad"),
            () -> w.client().watchTrades("bad"),
            () -> w.client().watchOrders("bad"),
            () -> w.client().watchMyTrades("bad"));
    for (Runnable r : bad) {
      assertThrows(BadSymbolException.class, r::run);
    }
  }

  @Test
  void privateChannels() {
    WsEnv w = wsEnv();
    Map<String, Object> order = Json.asMap(Fixtures.body("private_post_odr_orders"));
    CompletableFuture<Order> btc = async(() -> w.client().watchOrders("BTC/IRT"));
    CompletableFuture<Order> usdt = async(() -> w.client().watchOrders("USDT/IRT"));
    CompletableFuture<Order> any = async(() -> w.client().watchOrders(null));
    FakeTransport tr = w.transport();
    sleep(50);
    String ch = "user:order_info#TESTUSR1";
    Map<String, Object> u = new LinkedHashMap<>(order);
    u.putAll(map("event", "user_order_update", "symbol", "USDT_IRT", "id", "2"));
    Map<String, Object> b = new LinkedHashMap<>(order);
    b.putAll(map("event", "user_order_update", "symbol", "BTC_IRT", "id", "1"));
    tr.push(ch, u);
    tr.push(ch, b);
    assertEquals(
        List.of("1", "2", "2"), List.of(await(btc).id(), await(usdt).id(), await(any).id()));
    assertEquals(2, w.info().count(), "one shared identifier lookup + one connection token");

    Map<String, Object> fill =
        new LinkedHashMap<>(Json.asMap(Json.asList(Fixtures.body("private_get_odr_fills")).get(0)));
    CompletableFuture<Trade> mine = async(() -> w.client().watchMyTrades(""));
    sleep(30);
    fill.put("event", "user_match_update");
    tr.push(ch, fill);
    assertEquals("65375307", await(mine).id());
  }

  @Test
  void errors() throws Exception {
    WsEnv anon = wsEnv(b -> b.apiKey("").secretKey(""));
    assertThrows(AuthenticationException.class, () -> anon.client().watchOrders(null));
    CompletableFuture<List<Trade>> pub = async(() -> anon.client().watchTrades("BTC/IRT"));
    FakeTransport tr = anon.transport();
    assertNull(tr.tokens, "public-only clients connect without a token");
    tr.push(
        "matches:BTC_IRT",
        map("event", "matches_update", "symbol", "BTC_IRT", "matches", List.of()));
    assertEquals(List.of(), await(pub));

    WsEnv failing = wsEnv();
    failing.env().http().endpoint("credentials_post_usr_ws_info", Reply.of(503, null));
    assertThrows(ExchangeNotAvailableException.class, () -> failing.client().watchOrders(null));
    assertThrows(
        ExchangeNotAvailableException.class, () -> failing.client().watchTicker("BTC/IRT"));

    WsEnv sub = wsEnv();
    async(() -> sub.client().watchTicker("USDT/IRT"));
    FakeTransport str = sub.transport();
    sleep(30);
    str.failNext = new IllegalStateException("subscribe failed");
    assertThrows(IllegalStateException.class, () -> sub.client().watchTrades("USDT/IRT"));

    RequestTimeoutException timeout =
        assertThrows(
            RequestTimeoutException.class,
            () -> sub.client().watchOrderBook("USDT/IRT", Duration.ofMillis(30)));
    assertTrue(timeout.getMessage().contains("no update"));

    CompletableFuture<Object> waiting = new CompletableFuture<>();
    Thread t =
        Thread.ofVirtual()
            .start(
                () -> {
                  try {
                    sub.client().watchTrades("BTC/IRT");
                    waiting.complete("returned");
                  } catch (BitpinException e) {
                    waiting.complete(
                        e.getCause() instanceof InterruptedException
                            && Thread.currentThread().isInterrupted());
                  }
                });
    sleep(50);
    t.interrupt();
    assertEquals(true, waiting.get(2, TimeUnit.SECONDS));
  }

  @Test
  void queueDropsTheOldest() {
    BitpinWebSocket.Queue q = new BitpinWebSocket.Queue(2, d -> true);
    for (String p : List.of("0", "1", "2", "3")) {
      q.push(map("price", p));
    }
    assertEquals("2", q.next(null).get("price"));
    assertEquals("3", q.next(Duration.ofSeconds(1)).get("price"));
    assertThrows(RequestTimeoutException.class, () -> q.next(Duration.ZERO));
  }

  @Test
  void everyWatchMethodWithTimeouts() throws ExecutionException, InterruptedException {
    WsEnv w = wsEnv();
    Bitpin c = w.client();
    Duration t = Duration.ofSeconds(2);
    List<CompletableFuture<?>> done =
        List.of(
            async(() -> c.watchTicker("BTC/IRT", t)),
            async(() -> c.watchOHLCV("BTC/IRT", "1m", t)),
            async(() -> c.watchOrderBook("BTC/IRT", t)),
            async(() -> c.watchTrades("BTC/IRT", t)),
            async(() -> c.watchOrders("", t)),
            async(() -> c.watchMyTrades(null, t)));
    FakeTransport tr = w.transport();
    sleep(80);
    tr.push("market:BTC_IRT", WS_TICKER);
    tr.push(
        "market:BTC_IRT",
        map(
            "event",
            "candle_update",
            "symbol",
            "BTC_IRT",
            "candles",
            List.of(map("resolution", "1m", "ts", "1"))));
    tr.push("orderbook:BTC_IRT", map("event", "market_data", "symbol", "BTC_IRT"));
    tr.push("matches:BTC_IRT", map("event", "matches_update", "symbol", "BTC_IRT"));
    tr.push(
        "user:order_info#TESTUSR1",
        map("event", "user_order_update", "id", "1", "symbol", "BTC_IRT"));
    tr.push(
        "user:order_info#TESTUSR1",
        map("event", "user_match_update", "id", "1", "symbol", "BTC_IRT"));
    for (CompletableFuture<?> f : done) {
      assertNotNull(await(f));
    }
    c.close();
    assertTrue(tr.closed);
  }

  @Test
  void defaultTransportIsCentrifuge() {
    WsTransport t =
        new CentrifugeTransport("wss://example.invalid/connection/websocket", () -> "t");
    assertInstanceOf(CentrifugeTransport.class, t);
    t.close();
    assertInstanceOf(
        CentrifugeTransport.class,
        Config.builder().build().wsTransport().create("wss://example.invalid", null));
  }
}
