package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.Json.asList;
import static io.github.bitpindev.bitpin.Json.asMap;
import static io.github.bitpindev.bitpin.Json.str;
import static io.github.bitpindev.bitpin.Numbers.dec;
import static io.github.bitpindev.bitpin.Symbols.symbolOrRaw;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Consumer;
import java.util.function.Predicate;

/**
 * ccxt.pro-style watch methods over Bitpin's Centrifugo server. Each distinct watch (method,
 * symbol, timeframe) has its own queue, so every watcher sees its updates; two threads calling the
 * same watch split its updates.
 */
final class BitpinWebSocket {
  /** The updates of one watch; the oldest is dropped when full. */
  static final class Queue {
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notEmpty = lock.newCondition();
    private final ArrayDeque<Map<String, Object>> items = new ArrayDeque<>();
    private final int size;
    final Predicate<Map<String, Object>> accept;

    Queue(int size, Predicate<Map<String, Object>> accept) {
      this.size = size;
      this.accept = accept;
    }

    void push(Map<String, Object> item) {
      lock.lock();
      try {
        if (items.size() >= size) {
          items.pollFirst();
        }
        items.addLast(item);
        notEmpty.signal();
      } finally {
        lock.unlock();
      }
    }

    /** The next update; waits at most {@code timeout} (null: forever). */
    Map<String, Object> next(Duration timeout) {
      lock.lock();
      try {
        long nanos = timeout == null ? Long.MAX_VALUE : timeout.toNanos();
        while (items.isEmpty()) {
          if (timeout == null) {
            notEmpty.await();
          } else {
            if (nanos <= 0) {
              throw new RequestTimeoutException("no update within " + timeout);
            }
            nanos = notEmpty.awaitNanos(nanos);
          }
        }
        return items.pollFirst();
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new BitpinException("interrupted while waiting for an update", e);
      } finally {
        lock.unlock();
      }
    }
  }

  private record Key(String channel, String event, String filter) {}

  private final Bitpin client;
  private final WsTransport.Factory factory;
  private final int queueSize;

  private final ReentrantLock lock = new ReentrantLock();
  private WsTransport transport;
  private final Set<String> channels = new HashSet<>();
  private final Map<Key, Queue> queues = new HashMap<>();

  private final ReentrantLock userLock = new ReentrantLock();
  private String userId;

  BitpinWebSocket(Bitpin client, WsTransport.Factory factory, int queueSize) {
    this.client = client;
    this.factory = factory;
    this.queueSize = queueSize;
  }

  void close() {
    WsTransport t;
    lock.lock();
    try {
      t = transport;
      transport = null;
      channels.clear();
    } finally {
      lock.unlock();
    }
    if (t != null) {
      t.close();
    }
  }

  private Map<String, Object> wsInfo() {
    return asMap(client.request("credentials_post_usr_ws_info", null, null, client.credentials()));
  }

  Consumer<byte[]> onData(String channel) {
    return raw -> {
      Map<String, Object> data;
      try {
        if (!(Json.parse(raw) instanceof Map<?, ?> m)) {
          return;
        }
        data = asMap(m);
      } catch (IllegalArgumentException e) {
        return;
      }
      if (!(data.get("event") instanceof String event)) {
        return;
      }
      List<Queue> targets = new ArrayList<>();
      lock.lock();
      try {
        queues.forEach(
            (key, q) -> {
              if (key.channel().equals(channel)
                  && key.event().equals(event)
                  && q.accept.test(data)) {
                targets.add(q);
              }
            });
      } finally {
        lock.unlock();
      }
      targets.forEach(q -> q.push(data));
    };
  }

  private Map<String, Object> next(
      String channel,
      String event,
      String filter,
      Predicate<Map<String, Object>> accept,
      Duration timeout) {
    Queue q;
    lock.lock();
    try {
      q =
          queues.computeIfAbsent(
              new Key(channel, event, filter), k -> new Queue(queueSize, accept));
      if (transport == null) {
        WsTransport.TokenSource tokens =
            client.config().hasCredentials() ? () -> str(wsInfo().get("ws_token")) : null;
        WsTransport t = factory.create(client.config().wsUrl(), tokens);
        t.connect();
        transport = t;
      }
      if (channels.add(channel)) {
        try {
          transport.subscribe(channel, onData(channel));
        } catch (RuntimeException e) {
          channels.remove(channel);
          throw e;
        }
      }
    } finally {
      lock.unlock();
    }
    return q.next(timeout);
  }

  private String userChannel() {
    if (!client.config().hasCredentials()) {
      throw new AuthenticationException("apiKey and secretKey are required for private channels");
    }
    userLock.lock(); // one lookup shared by every concurrent watcher (ws-info: 10 per minute)
    try {
      if (userId == null || userId.isEmpty()) {
        userId = str(wsInfo().get("user_identifier"));
      }
      return Spec.WS_CHANNELS.get("user_orders").replace("{user_identifier}", userId);
    } finally {
      userLock.unlock();
    }
  }

  private static String channelFor(String kind, String symbol) {
    return Spec.WS_CHANNELS.get(kind).replace("{symbol}", Symbols.marketId(symbol));
  }

  Ticker watchTicker(String symbol, Duration timeout) {
    Map<String, Object> data =
        next(channelFor("market", symbol), "currency_price_update", "", d -> true, timeout);
    BigDecimal time = dec(data.get("time"));
    Long ts = time == null ? null : time.longValue();
    BigDecimal last = dec(data.get("price"));
    return new Ticker(
        symbolOrRaw(data.get("symbol")),
        ts,
        Parse.msToIso(ts),
        dec(data.get("max")),
        dec(data.get("min")),
        null,
        null,
        last,
        last,
        null,
        null,
        Parse.ratioToPercent(data.get("change")),
        dec(data.get("mean")),
        dec(data.get("amount")),
        dec(data.get("value")),
        data);
  }

  List<OHLCV> watchOHLCV(String symbol, String timeframe, Duration timeout) {
    if (!Bitpin.TIMEFRAMES.containsKey(timeframe)) {
      throw new BadRequestException("timeframe \"" + timeframe + "\" is not supported");
    }
    Predicate<Object> match = c -> str(asMap(c).get("resolution")).equals(timeframe);
    Map<String, Object> data =
        next(
            channelFor("market", symbol),
            "candle_update",
            timeframe,
            d -> asList(d.get("candles")).stream().anyMatch(match),
            timeout);
    return asList(data.get("candles")).stream()
        .filter(match)
        .map(c -> Parse.ohlcv(asMap(c)))
        .toList();
  }

  OrderBook watchOrderBook(String symbol, Duration timeout) {
    Map<String, Object> data =
        next(channelFor("orderbook", symbol), "market_data", "", d -> true, timeout);
    return Parse.orderBook(
        data, symbolOrRaw(data.get("symbol")), Parse.isoToMs(data.get("event_time")));
  }

  List<Trade> watchTrades(String symbol, Duration timeout) {
    Map<String, Object> data =
        next(channelFor("matches", symbol), "matches_update", "", d -> true, timeout);
    String unified = symbolOrRaw(data.get("symbol"));
    return asList(data.get("matches")).stream().map(r -> Parse.trade(asMap(r), unified)).toList();
  }

  private Map<String, Object> privateUpdate(String event, String symbol, Duration timeout) {
    String channel = userChannel();
    String wanted = symbol == null || symbol.isEmpty() ? "" : Symbols.marketId(symbol);
    return next(
        channel,
        event,
        wanted.isEmpty() ? "*" : wanted,
        d -> wanted.isEmpty() || str(d.get("symbol")).equals(wanted),
        timeout);
  }

  Order watchOrders(String symbol, Duration timeout) {
    return Parse.order(privateUpdate("user_order_update", symbol, timeout));
  }

  Trade watchMyTrades(String symbol, Duration timeout) {
    return Parse.myTrade(privateUpdate("user_match_update", symbol, timeout));
  }
}
