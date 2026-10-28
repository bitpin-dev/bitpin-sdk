package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.Json.asList;
import static io.github.bitpindev.bitpin.Json.asMap;
import static io.github.bitpindev.bitpin.Json.str;
import static io.github.bitpindev.bitpin.Json.truthy;

import java.io.IOException;
import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.locks.ReentrantLock;

/**
 * The Bitpin exchange client. Method names, arguments and results follow ccxt; prices and amounts
 * are {@link BigDecimal}. Every method blocks until the answer arrives (run many at once on virtual
 * threads) and the client is safe to share between threads.
 *
 * <pre>{@code
 * try (Bitpin client = new Bitpin(Config.fromEnv().build())) {
 *   Ticker ticker = client.fetchTicker("BTC/IRT");
 *   Order order = client.createOrder("USDT/IRT", "limit", "buy",
 *       new BigDecimal("10"), new BigDecimal("90000"), Map.of("clientOrderId", "bot-1"));
 * } catch (InsufficientFundsException e) {
 *   // ...
 * }
 * }</pre>
 *
 * <p>Bitpin has no sandbox: every call reaches the real exchange.
 */
public final class Bitpin implements AutoCloseable {
  /** The candle resolutions in seconds (ccxt names; 1m is a minute, 1M a month). */
  public static final Map<String, Long> TIMEFRAMES =
      Map.ofEntries(
          Map.entry("1m", 60L),
          Map.entry("5m", 300L),
          Map.entry("15m", 900L),
          Map.entry("30m", 1800L),
          Map.entry("1h", 3600L),
          Map.entry("3h", 10800L),
          Map.entry("4h", 14400L),
          Map.entry("6h", 21600L),
          Map.entry("1d", 86400L),
          Map.entry("1w", 604800L),
          Map.entry("1M", 2592000L));

  private static final double MAX_RATE_LIMIT_WAIT = 5.0;
  private static final int DEFAULT_OHLCV_LIMIT = 500;
  private static final List<String> ORDER_TYPES = List.of("limit", "market", "stop_limit", "oco");
  private static final Map<String, String> PARAM_ALIASES =
      Map.of(
          "clientOrderId", "identifier",
          "stopPrice", "stop_price",
          "triggerPrice", "stop_price",
          "takeProfitPrice", "oco_target_price",
          "ocoTargetPrice", "oco_target_price",
          "quoteAmount", "quote_amount",
          "cost", "quote_amount");
  private static final Map<String, String> MAX_PAGE_SIZE =
      Map.of(
          "private_get_odr_orders", "orders_max_page_size",
          "private_get_odr_fills", "fills_max_page_size",
          "private_get_wlt_wallets", "wallets_max_page_size",
          "private_get_wlt_deposits", "wallet_lists_max_page_size",
          "private_get_wlt_withdraws", "wallet_lists_max_page_size");
  private static final DateTimeFormatter ISO_PARAM =
      DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss.SSS'+00:00'").withZone(ZoneOffset.UTC);
  private static final DateTimeFormatter DAY =
      DateTimeFormatter.ofPattern("uuuu-MM-dd").withZone(ZoneOffset.UTC);

  /** {@code bitpin}, as in ccxt. */
  public final String id = "bitpin";

  /** {@code Bitpin}, as in ccxt. */
  public final String name = "Bitpin";

  private final Config cfg;
  private final RateLimiter limiter;
  private final ReentrantLock authLock = new ReentrantLock();
  private final TokenState tokens;
  private boolean loaded;
  private String keyId;

  private final ReentrantLock marketsLock = new ReentrantLock();
  private volatile Map<String, Market> markets;
  private volatile Map<String, Market> marketsById;

  private final ReentrantLock wsLock = new ReentrantLock();
  private BitpinWebSocket ws;

  /** A client for public endpoints with the default settings. */
  public Bitpin() {
    this(Config.builder().build());
  }

  /** A client with these settings. */
  public Bitpin(Config config) {
    this.cfg = Objects.requireNonNull(config, "config");
    this.limiter = new RateLimiter(config.rateLimits(), this::now);
    this.tokens = new TokenState(this::now);
  }

  double now() {
    Instant t = cfg.clock().instant();
    return t.getEpochSecond() + t.getNano() / 1e9;
  }

  /** Hides the credentials. */
  @Override
  public String toString() {
    return "Bitpin{" + cfg + "}";
  }

  /** The effective settings (domain, URLs, …). */
  public Config config() {
    return cfg;
  }

  /** The ccxt capability map: false means Bitpin doesn't offer it yet. */
  public Map<String, Boolean> has() {
    return new TreeMap<>(Spec.HAS);
  }

  /** The effective per-bucket limits. */
  public Map<String, RateLimit> rateLimits() {
    return cfg.rateLimits();
  }

  /** Disconnects the WebSocket, if one was opened. */
  @Override
  public void close() {
    BitpinWebSocket open;
    wsLock.lock();
    try {
      open = ws;
      ws = null;
    } finally {
      wsLock.unlock();
    }
    if (open != null) {
      open.close();
    }
  }

  // --- transport -------------------------------------------------------------------------------

  void sleep(double seconds) {
    try {
      cfg.sleeper().sleep(Duration.ofNanos((long) (seconds * 1e9)));
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new BitpinException("interrupted while waiting", e);
    }
  }

  /**
   * Calls one endpoint by its spec id (e.g. {@code public_get_mkt_tickers}) and returns the decoded
   * JSON. It rate-limits, authenticates, maps errors, and retries only when safe.
   *
   * @param pathParams values for the path's {@code {placeholders}}, or null
   * @param params query parameters, or null; null values are skipped
   * @param body the JSON body, or null; numbers are sent as plain decimal strings
   */
  public Object request(
      String endpointId, Map<String, ?> pathParams, Map<String, ?> params, Object body) {
    Requests.Built req = Requests.build(cfg, endpointId, pathParams, params, body);
    boolean reauthenticated = false;
    int attempt = 0;
    while (true) {
      String token = "";
      if (req.endpoint().auth().equals("private")) {
        token = accessToken();
      }
      try {
        return send(req, token);
      } catch (AuthenticationException e) {
        if (!req.endpoint().auth().equals("private") || reauthenticated) {
          throw e;
        }
        reauthenticated = true;
        authLock.lock();
        try {
          tokens.expireAccess(token);
        } finally {
          authLock.unlock();
        }
      } catch (NetworkException e) {
        double wait = retryDelay(req, e, attempt);
        if (wait < 0) {
          throw e;
        }
        attempt++;
        sleep(wait);
      }
    }
  }

  private double retryDelay(Requests.Built req, NetworkException e, int attempt) {
    if (!req.endpoint().idempotent() || attempt >= cfg.maxRetries()) {
      return -1;
    }
    if (e instanceof RateLimitExceededException) {
      double after = e.retryAfter().orElse(-1);
      return after < 0 || after > MAX_RATE_LIMIT_WAIT ? -1 : after;
    }
    return 0.5 * (1L << attempt);
  }

  private Object send(Requests.Built req, String token) {
    String id = req.endpoint().id();
    if (cfg.rateLimitEnabled()) {
      double wait = limiter.reserve(req.endpoint().buckets());
      if (wait > 0) {
        sleep(wait);
      }
    }
    Map<String, String> headers = new LinkedHashMap<>();
    headers.put("Accept", "application/json");
    headers.put("User-Agent", cfg.userAgent());
    if (req.body() != null) {
      headers.put("Content-Type", "application/json");
    }
    if (!token.isEmpty()) {
      headers.put("Authorization", "Bearer " + token);
    }
    RestTransport.Response resp;
    try {
      resp =
          cfg.restTransport()
              .send(
                  new RestTransport.Request(
                      req.endpoint().method(),
                      URI.create(req.url()),
                      headers,
                      req.body(),
                      cfg.timeout()));
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new BitpinException(id + ": interrupted", e);
    } catch (IOException e) {
      boolean timeout = e instanceof HttpTimeoutException;
      String message = id + (timeout ? ": request timed out" : ": network error");
      // The request of a credentials call holds the secret key: never chain its transport error.
      Throwable cause = req.endpoint().auth().equals("credentials") ? null : e;
      BitpinException err =
          timeout
              ? new RequestTimeoutException(message, cause)
              : new NetworkException(message, cause);
      throw err.endpoint(id);
    }
    byte[] raw = resp.body() == null ? new byte[0] : resp.body();
    Object data = null;
    boolean valid = true;
    if (raw.length > 0) {
      try {
        data = Json.parse(raw);
      } catch (IllegalArgumentException e) {
        valid = false;
        data = new String(raw, StandardCharsets.UTF_8);
      }
    }
    if (resp.status() >= 400) {
      throw Errors.map(id, resp.status(), data, resp.header("Retry-After"));
    }
    if (!valid) {
      throw new ExchangeException(id + ": invalid JSON in response")
          .response(resp.status(), data, id);
    }
    return data;
  }

  // --- authentication --------------------------------------------------------------------------

  Map<String, Object> credentials() {
    if (!cfg.hasCredentials()) {
      throw new AuthenticationException("apiKey and secretKey are required for private endpoints");
    }
    Map<String, Object> creds = new LinkedHashMap<>();
    creds.put("api_key", cfg.apiKey());
    creds.put("secret_key", cfg.secretKey());
    return creds;
  }

  private String accessToken() {
    authLock.lock();
    try {
      Map<String, Object> creds = credentials();
      if (keyId == null) {
        keyId = TokenStore.keyId(cfg.apiKey()); // PBKDF2 is slow on purpose; derive it once
      }
      if (!loaded) {
        loaded = true;
        try {
          cfg.tokenStore().load(keyId).ifPresent(t -> tokens.tokens = t);
        } catch (RuntimeException e) {
          // an unreadable store: authenticate again
        }
      }
      TokenState.Action action = tokens.action();
      if (action == TokenState.Action.REFRESH) {
        Requests.Built req =
            Requests.build(
                cfg,
                "credentials_post_usr_refresh_token",
                null,
                null,
                Map.of("refresh", tokens.tokens.refresh()));
        try {
          Object data = send(req, "");
          cfg.tokenStore().save(keyId, tokens.setAccess(str(asMap(data).get("access"))));
          action = TokenState.Action.OK;
        } catch (AuthenticationException | BadRequestException e) {
          action = TokenState.Action.AUTHENTICATE;
        }
      }
      if (action == TokenState.Action.AUTHENTICATE) {
        Requests.Built req =
            Requests.build(cfg, "credentials_post_usr_authenticate", null, null, creds);
        Map<String, Object> m = asMap(send(req, ""));
        cfg.tokenStore().save(keyId, tokens.setTokens(str(m.get("access")), str(m.get("refresh"))));
      }
      return tokens.tokens.access();
    } finally {
      authLock.unlock();
    }
  }

  // --- helpers ---------------------------------------------------------------------------------

  private List<Object> list(String endpointId, Map<String, ?> pathParams, Map<String, ?> params) {
    return asList(request(endpointId, pathParams, params, null));
  }

  private static String optionalMarketId(String symbol) {
    return symbol == null || symbol.isEmpty() ? null : Symbols.marketId(symbol);
  }

  /** {@code base} without null values, then {@code extra} on top. */
  private static Map<String, Object> merge(Map<String, ?> base, Map<String, ?> extra) {
    Map<String, Object> out = new LinkedHashMap<>();
    if (base != null) {
      base.forEach(
          (k, v) -> {
            if (v != null) {
              out.put(k, v);
            }
          });
    }
    if (extra != null) {
      out.putAll(extra);
    }
    return out;
  }

  /** A map that keeps null values, unlike {@link Map#of}. */
  private static Map<String, Object> params(Object... pairs) {
    Map<String, Object> out = new LinkedHashMap<>();
    for (int i = 0; i < pairs.length; i += 2) {
      out.put((String) pairs[i], pairs[i + 1]);
    }
    return out;
  }

  private static String isoParam(Long ms) {
    return ms == null ? null : ISO_PARAM.format(Instant.ofEpochMilli(ms));
  }

  private static <T> List<T> mapRows(
      List<Object> rows, java.util.function.Function<Map<String, Object>, T> parse) {
    List<T> out = new ArrayList<>(rows.size());
    for (Object r : rows) {
      out.add(parse.apply(asMap(r)));
    }
    return out;
  }

  private static long ms(Long value) {
    return value == null ? 0 : value;
  }

  private static long idNumber(String id) {
    try {
      return Long.parseLong(id);
    } catch (NumberFormatException e) {
      return 0;
    }
  }

  // --- markets ---------------------------------------------------------------------------------

  /** Every market, with precision (tick sizes) and {@code active}. */
  public List<Market> fetchMarkets() {
    return mapRows(list("public_get_mkt_markets", null, null), Parse::market);
  }

  /** Fetches markets once and caches them by symbol. */
  public Map<String, Market> loadMarkets() {
    return loadMarkets(false);
  }

  /** Fetches markets once (or again with {@code reload}) and caches them by symbol. */
  public Map<String, Market> loadMarkets(boolean reload) {
    Map<String, Market> cached = markets;
    if (cached != null && !reload) {
      return cached;
    }
    List<Market> fetched = fetchMarkets();
    Map<String, Market> bySymbol = new LinkedHashMap<>();
    Map<String, Market> byId = new LinkedHashMap<>();
    for (Market m : fetched) {
      bySymbol.put(m.symbol(), m);
      byId.put(m.id(), m);
    }
    marketsLock.lock();
    try {
      marketsById = Map.copyOf(byId);
      markets = java.util.Collections.unmodifiableMap(bySymbol);
      return markets;
    } finally {
      marketsLock.unlock();
    }
  }

  /** A cached market for {@code BTC/IRT} or {@code BTC_IRT}. Call {@link #loadMarkets()} first. */
  public Market market(String symbol) {
    Map<String, Market> byId = marketsById;
    if (byId == null) {
      throw new BitpinException("markets not loaded; call loadMarkets first");
    }
    String id = Symbols.marketId(symbol);
    Market m = byId.get(id);
    if (m == null) {
      throw new BadSymbolException("unknown market " + Symbols.symbolOrRaw(id));
    }
    return m;
  }

  /** Every currency by code. */
  public Map<String, Currency> fetchCurrencies() {
    Map<String, Currency> out = new LinkedHashMap<>();
    for (Currency c : mapRows(list("public_get_mkt_currencies", null, null), Parse::currency)) {
      out.put(c.code(), c);
    }
    return out;
  }

  /** Every network. */
  public List<Network> fetchNetworks() {
    return fetchNetworks(null);
  }

  /** Every network; params: {@code code}, {@code can_deposit}, {@code can_withdraw}. */
  public List<Network> fetchNetworks(Map<String, ?> params) {
    return mapRows(list("public_get_mkt_networks", null, params), Parse::network);
  }

  /** {@code {symbol: suspended}} for your account (2 requests per minute). */
  public Map<String, Boolean> fetchMarketSuspensions() {
    Map<String, Boolean> out = new LinkedHashMap<>();
    for (Object r : list("private_get_mkt_markets_suspensions", null, null)) {
      Map<String, Object> m = asMap(r);
      out.put(Symbols.symbolOrRaw(m.get("code")), truthy(m.get("suspended")));
    }
    return out;
  }

  // --- tickers, order book, trades, candles ----------------------------------------------------

  /** Tickers by symbol; pass symbols to keep only those. */
  public Map<String, Ticker> fetchTickers(String... symbols) {
    return fetchTickers(Arrays.asList(symbols));
  }

  /** Tickers by symbol; an empty collection means every market. */
  public Map<String, Ticker> fetchTickers(Collection<String> symbols) {
    Set<String> wanted = new HashSet<>();
    for (String s : symbols) {
      wanted.add(Symbols.symbolOrRaw(Symbols.marketId(s)));
    }
    Map<String, Ticker> out = new LinkedHashMap<>();
    for (Ticker t : mapRows(list("public_get_mkt_tickers", null, null), Parse::ticker)) {
      if (wanted.isEmpty() || wanted.contains(t.symbol())) {
        out.put(t.symbol(), t);
      }
    }
    return out;
  }

  /** One market's 24-hour ticker. */
  public Ticker fetchTicker(String symbol) {
    String unified = Symbols.symbolOrRaw(Symbols.marketId(symbol));
    Ticker t = fetchTickers(unified).get(unified);
    if (t == null) {
      throw new BadSymbolException("no ticker for " + unified);
    }
    return t;
  }

  /** The top 20 levels of the book. */
  public OrderBook fetchOrderBook(String symbol) {
    return fetchOrderBook(symbol, null);
  }

  /** The top of the book: 20 levels when {@code limit} is null, at most 50. */
  public OrderBook fetchOrderBook(String symbol, Integer limit) {
    int max = Spec.CONSTANTS.get("orderbook_max_limit");
    if (limit != null && (limit < 1 || limit > max)) {
      throw new BadRequestException("order book limit must be 1.." + max);
    }
    String id = Symbols.marketId(symbol);
    Object data =
        request(
            "public_get_mth_orderbook_symbol", Map.of("symbol", id), params("limit", limit), null);
    return Parse.orderBook(asMap(data), Symbols.symbolOrRaw(id), null);
  }

  /** Recent public trades, oldest first. */
  public List<Trade> fetchTrades(String symbol) {
    return fetchTrades(symbol, null, null);
  }

  /** Recent public trades, oldest first; {@code since} (ms) and {@code limit} filter locally. */
  public List<Trade> fetchTrades(String symbol, Long since, Integer limit) {
    String id = Symbols.marketId(symbol);
    String unified = Symbols.symbolOrRaw(id);
    List<Trade> trades = new ArrayList<>();
    for (Object r : list("public_get_mth_matches_symbol", Map.of("symbol", id), null)) {
      Trade t = Parse.trade(asMap(r), unified);
      if (since == null || (t.timestamp() != null && t.timestamp() >= since)) {
        trades.add(t);
      }
    }
    trades.sort(Comparator.comparingLong(t -> ms(t.timestamp())));
    if (limit != null && limit > 0 && trades.size() > limit) {
      trades = trades.subList(trades.size() - limit, trades.size());
    }
    return List.copyOf(trades);
  }

  /** The latest 500 candles of {@code timeframe}, oldest first. */
  public List<OHLCV> fetchOHLCV(String symbol, String timeframe) {
    return fetchOHLCV(symbol, timeframe, null, null, null);
  }

  /**
   * Candles, oldest first. Without {@code since}: the latest {@code limit} candles (500 by
   * default); with it, the {@code limit} candles from {@code since} (ms).
   */
  public List<OHLCV> fetchOHLCV(
      String symbol, String timeframe, Long since, Integer limit, Map<String, ?> params) {
    String tf = timeframe == null || timeframe.isEmpty() ? "30m" : timeframe;
    Long step = TIMEFRAMES.get(tf);
    if (step == null) {
      throw new BadRequestException("timeframe \"" + tf + "\" is not supported");
    }
    if (limit != null && limit < 1) {
      throw new BadRequestException("fetchOHLCV limit must be at least 1");
    }
    int count = limit == null ? DEFAULT_OHLCV_LIMIT : limit;
    int max = Spec.CONSTANTS.get("candles_max_per_request");
    if (count > max) {
      throw new BadRequestException("at most " + max + " candles per request");
    }
    String id = Symbols.marketId(symbol);
    long start;
    long end;
    if (since == null) {
      end = cfg.clock().instant().getEpochSecond();
      start = end - count * step;
    } else {
      start = since / 1000;
      end = start + count * step;
    }
    List<OHLCV> candles =
        mapRows(
            list(
                "public_get_mkt_candles",
                null,
                merge(params("symbol", id, "res", tf, "from", start, "to", end), params)),
            Parse::ohlcv);
    if (candles.size() > count) {
      candles =
          since == null
              ? candles.subList(candles.size() - count, candles.size())
              : candles.subList(0, count);
    }
    return List.copyOf(candles);
  }

  /** Your maker/taker fees per market, as ratios (0.003 = 0.3 %). */
  public Map<String, TradingFee> fetchTradingFees() {
    Map<String, TradingFee> out = new LinkedHashMap<>();
    for (TradingFee f :
        mapRows(list("private_get_mkt_commissions", null, null), Parse::tradingFee)) {
      out.put(f.symbol(), f);
    }
    return out;
  }

  /** One market's fee. */
  public TradingFee fetchTradingFee(String symbol) {
    String unified = Symbols.symbolOrRaw(Symbols.marketId(symbol));
    TradingFee f = fetchTradingFees().get(unified);
    if (f == null) {
      throw new BadSymbolException("no trading fee for " + unified);
    }
    return f;
  }

  // --- orders ----------------------------------------------------------------------------------

  private static void checkPositive(String name, Object value) {
    if (value == null) {
      return;
    }
    BigDecimal d;
    try {
      d = Numbers.toDecimal(value);
    } catch (IllegalArgumentException e) {
      throw new InvalidOrderException(name + " must be positive", e);
    }
    if (d != null && d.signum() <= 0) {
      throw new InvalidOrderException(name + " must be positive");
    }
  }

  /** Validates an order locally and builds the request body. */
  static Map<String, Object> orderBody(
      String symbol,
      String type,
      String side,
      BigDecimal amount,
      BigDecimal price,
      Map<String, ?> params) {
    if (!ORDER_TYPES.contains(type)) {
      throw new InvalidOrderException(
          "order type must be one of " + String.join(", ", ORDER_TYPES));
    }
    if (!"buy".equals(side) && !"sell".equals(side)) {
      throw new InvalidOrderException("order side must be 'buy' or 'sell'");
    }
    String id = Symbols.marketId(symbol);
    Map<String, Object> extra = new LinkedHashMap<>();
    if (params != null) {
      for (Map.Entry<String, ?> p : new TreeMap<String, Object>(params).entrySet()) {
        String key = PARAM_ALIASES.getOrDefault(p.getKey(), p.getKey());
        if (extra.containsKey(key)
            && !String.valueOf(extra.get(key)).equals(String.valueOf(p.getValue()))) {
          throw new InvalidOrderException(
              "params set " + key + " twice (\"" + p.getKey() + "\"); pass only one of both");
        }
        extra.put(key, p.getValue());
      }
    }
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("symbol", id);
    body.put("type", type);
    body.put("side", side);
    if (amount != null) {
      body.put("base_amount", amount);
    }
    if (price != null && !type.equals("market")) {
      body.put("price", price);
    }
    extra.forEach(
        (k, v) -> {
          if (v != null) {
            body.put(k, v);
          }
        });
    checkPositive("amount", body.get("base_amount"));
    checkPositive("price", body.get("price"));
    checkPositive("params.stopPrice", body.get("stop_price"));
    checkPositive("params.takeProfitPrice", body.get("oco_target_price"));
    checkPositive("params.quoteAmount", body.get("quote_amount"));
    boolean hasBase = body.containsKey("base_amount");
    boolean hasQuote = body.containsKey("quote_amount");
    if (type.equals("market")) {
      if (hasBase && hasQuote) {
        throw new InvalidOrderException("market orders take only one of amount or quoteAmount");
      }
      if (!hasBase && !hasQuote) {
        throw new InvalidOrderException("market orders need amount or params.quoteAmount");
      }
      return body;
    }
    if (!hasBase) {
      throw new InvalidOrderException(type + " orders need an amount");
    }
    if (!body.containsKey("price")) {
      throw new InvalidOrderException(type + " orders need a price");
    }
    if (!body.containsKey("stop_price") && (type.equals("stop_limit") || type.equals("oco"))) {
      throw new InvalidOrderException(type + " orders need params.stopPrice");
    }
    if (!body.containsKey("oco_target_price") && type.equals("oco")) {
      throw new InvalidOrderException("oco orders need params.takeProfitPrice");
    }
    return body;
  }

  /**
   * Places an order without params. See {@link #createOrder(String, String, String, BigDecimal,
   * BigDecimal, Map)}.
   */
  public Order createOrder(
      String symbol, String type, String side, BigDecimal amount, BigDecimal price) {
    return createOrder(symbol, type, side, amount, price, null);
  }

  /**
   * Places an order. It is never retried.
   *
   * @param type {@code limit}, {@code market}, {@code stop_limit} or {@code oco}
   * @param side {@code buy} or {@code sell}
   * @param amount in the base currency; null for a market order by {@code quoteAmount}
   * @param price null for market orders
   * @param params {@code clientOrderId}, {@code quoteAmount} (market by quote), {@code
   *     stopPrice}/{@code triggerPrice}, {@code takeProfitPrice} (oco), or raw Bitpin fields
   */
  public Order createOrder(
      String symbol,
      String type,
      String side,
      BigDecimal amount,
      BigDecimal price,
      Map<String, ?> params) {
    Map<String, Object> body = orderBody(symbol, type, side, amount, price, params);
    return Parse.order(asMap(request("private_post_odr_orders", null, null, body)));
  }

  /** Places up to 10 orders in one atomic request. */
  public List<Order> createOrders(List<OrderRequest> orders) {
    int max = Spec.CONSTANTS.get("bulk_orders_max");
    if (orders == null || orders.isEmpty()) {
      throw new BadRequestException("createOrders needs at least one order");
    }
    if (orders.size() > max) {
      throw new BadRequestException("createOrders takes at most " + max + " orders");
    }
    List<Object> bodies = new ArrayList<>();
    for (OrderRequest o : orders) {
      bodies.add(orderBody(o.symbol(), o.type(), o.side(), o.amount(), o.price(), o.params()));
    }
    return Parse.bulkOrders(request("private_post_odr_orders_bulk", null, null, bodies));
  }

  /** One of your orders. */
  public Order fetchOrder(String id) {
    return Parse.order(asMap(request("private_get_odr_orders_id", Map.of("id", id), null, null)));
  }

  private static void sortOrders(List<Order> orders) {
    orders.sort(
        Comparator.comparingLong((Order o) -> ms(o.timestamp()))
            .thenComparingLong(o -> idNumber(o.id())));
  }

  /** Your active orders and the ones closed in the last 7 days, oldest first. */
  public List<Order> fetchOrders() {
    return fetchOrders(null, null, null, null);
  }

  /** Like {@link #fetchOrders()}, in one market. */
  public List<Order> fetchOrders(String symbol) {
    return fetchOrders(symbol, null, null, null);
  }

  /**
   * Your active orders and the ones closed in the last 7 days, oldest first.
   *
   * @param symbol null for every market
   * @param since ms, or null
   * @param limit rows per page, or null
   * @param params Bitpin filters ({@code state}, {@code side}, …), {@code paginate} (boolean) and
   *     {@code maxPages}
   */
  public List<Order> fetchOrders(String symbol, Long since, Integer limit, Map<String, ?> params) {
    List<Object> rows =
        paged(
            "private_get_odr_orders",
            params("symbol", optionalMarketId(symbol), "start", isoParam(since), "limit", limit),
            params);
    List<Order> orders = new ArrayList<>(mapRows(rows, Parse::order));
    sortOrders(orders);
    return List.copyOf(orders);
  }

  /** Your initial and active orders. */
  public List<Order> fetchOpenOrders() {
    return fetchOpenOrders(null, null, null, null);
  }

  /** Your initial and active orders in one market. */
  public List<Order> fetchOpenOrders(String symbol) {
    return fetchOpenOrders(symbol, null, null, null);
  }

  /**
   * Your initial and active orders; arguments as in {@link #fetchOrders(String, Long, Integer,
   * Map)}.
   */
  public List<Order> fetchOpenOrders(
      String symbol, Long since, Integer limit, Map<String, ?> params) {
    return fetchOrders(
        symbol, since, limit, merge(params, Map.of("state", List.of("initial", "active"))));
  }

  /** Your orders closed in the last 7 days; older ones: {@link #fetchOrderHistory}. */
  public List<Order> fetchClosedOrders() {
    return fetchClosedOrders(null, null, null, null);
  }

  /** Your orders closed in the last 7 days in one market. */
  public List<Order> fetchClosedOrders(String symbol) {
    return fetchClosedOrders(symbol, null, null, null);
  }

  /**
   * Your orders closed in the last 7 days; arguments as in {@link #fetchOrders(String, Long,
   * Integer, Map)}.
   */
  public List<Order> fetchClosedOrders(
      String symbol, Long since, Integer limit, Map<String, ?> params) {
    return fetchOrders(symbol, since, limit, merge(params, Map.of("state", "closed")));
  }

  /** Asks the engine to cancel; the order closes a moment later. Never retried. */
  public void cancelOrder(String id) {
    request("private_delete_odr_orders_id", Map.of("id", id), null, null);
  }

  /** Cancels by your {@code clientOrderId}. Never retried. */
  public void cancelOrderByIdentifier(String identifier) {
    request(
        "private_delete_odr_orders_identifier_identifier",
        Map.of("identifier", identifier),
        null,
        null);
  }

  /** Cancels up to 10 orders by ids or by identifiers: pass exactly one of both, the other null. */
  public CancelResult cancelOrders(List<String> ids, List<String> identifiers) {
    boolean byIds = ids != null && !ids.isEmpty();
    boolean byIdentifiers = identifiers != null && !identifiers.isEmpty();
    if (byIds == byIdentifiers) {
      throw new BadRequestException("cancelOrders needs exactly one of ids or identifiers");
    }
    List<String> values = byIds ? ids : identifiers;
    int max = Spec.CONSTANTS.get("bulk_orders_max");
    if (values.size() > max) {
      throw new BadRequestException("cancelOrders takes at most " + max + " orders");
    }
    Map<String, Object> m =
        asMap(
            request(
                "private_delete_odr_orders_bulk",
                null,
                null,
                Map.of(byIds ? "ids" : "identifiers", values)));
    return new CancelResult(
        strings(m.get("canceled_orders")), strings(m.get("not_canceled_orders")), m);
  }

  private static List<String> strings(Object value) {
    return asList(value).stream().map(Json::str).toList();
  }

  /** Your fills from the last 24 hours, oldest first. */
  public List<Trade> fetchMyTrades() {
    return fetchMyTrades(null, null, null, null);
  }

  /** Your fills from the last 24 hours in one market, oldest first. */
  public List<Trade> fetchMyTrades(String symbol) {
    return fetchMyTrades(symbol, null, null, null);
  }

  /** Your fills from the last 24 hours, oldest first; {@code params} takes {@code paginate}. */
  public List<Trade> fetchMyTrades(
      String symbol, Long since, Integer limit, Map<String, ?> params) {
    long oldest =
        (cfg.clock().instant().getEpochSecond() - Spec.CONSTANTS.get("fills_max_age_seconds"))
            * 1000;
    if (since != null && since < oldest) {
      throw new BadRequestException("fetchMyTrades only covers the last 24 hours");
    }
    List<Object> rows =
        paged(
            "private_get_odr_fills",
            params(
                "symbol",
                optionalMarketId(symbol),
                "start",
                since == null ? null : since / 1000,
                "limit",
                limit),
            params);
    List<Trade> trades = new ArrayList<>(mapRows(rows, Parse::myTrade));
    trades.sort(
        Comparator.comparingLong((Trade t) -> ms(t.timestamp()))
            .thenComparingLong(t -> idNumber(t.id())));
    return List.copyOf(trades);
  }

  /** Your closed orders with at least one fill, newest first. */
  public List<Order> fetchOrderHistory() {
    return fetchOrderHistory(null, null, null, null, null);
  }

  /**
   * Your closed orders with at least one fill, newest first.
   *
   * @param since ms, or null
   * @param until ms, or null; the range is at most 90 days
   * @param limit 1..200, or null
   * @param params {@code side}, {@code type}, {@code service}, and {@code paginate} to follow the
   *     cursor through every page
   */
  public List<Order> fetchOrderHistory(
      String symbol, Long since, Long until, Integer limit, Map<String, ?> params) {
    int max = Spec.CONSTANTS.get("order_history_max_limit");
    if (limit != null && (limit < 1 || limit > max)) {
      throw new BadRequestException("order history limit must be 1.." + max);
    }
    if (since != null && until != null) {
      if (since >= until) {
        throw new BadRequestException("order history since must be before until");
      }
      if (until - since > Spec.CONSTANTS.get("order_history_max_range_days") * 86_400_000L) {
        throw new BadRequestException("order history range is at most 90 days");
      }
    }
    String id = optionalMarketId(symbol);
    Map<String, Object> extra = merge(null, params);
    boolean paginate = truthy(extra.remove("paginate"));
    Map<String, Object> filters = merge(params("symbol", id, "limit", limit), extra);
    Map<String, Object> query = merge(filters, params("start", since, "end", until));
    List<Order> orders = new ArrayList<>();
    Set<String> seenIds = new HashSet<>();
    Set<String> seenCursors = new HashSet<>();
    while (true) {
      Map<String, Object> m = asMap(request("private_get_odr_order_history", null, query, null));
      for (Object r : asList(m.get("results"))) {
        Order o = Parse.historyOrder(asMap(r));
        if (seenIds.add(o.id())) {
          orders.add(o);
        }
      }
      String cursor = str(m.get("next_cursor"));
      if (!paginate || !truthy(m.get("has_next")) || cursor.isEmpty() || !seenCursors.add(cursor)) {
        return List.copyOf(orders);
      }
      // The cursor replaces start/end; the server doesn't keep the other filters.
      query = merge(filters, Map.of("cursor", cursor));
    }
  }

  // --- wallet ----------------------------------------------------------------------------------

  /** The main wallet's balances. */
  public Balances fetchBalance() {
    return fetchBalance(null);
  }

  /** Balances; params: {@code service} for wallets other than {@code main}. */
  public Balances fetchBalance(Map<String, ?> params) {
    Map<String, Object> query =
        merge(
            params("service", "main", "limit", Spec.CONSTANTS.get("wallets_max_page_size")),
            params);
    return Parse.balance(allPages("private_get_wlt_wallets", query));
  }

  /** Your bank accounts; pass an {@code id} as {@code accountNumber} to withdraw IRT. */
  public List<BankAccount> fetchBankAccounts() {
    return mapRows(list("private_get_wlt_account_numbers", null, null), Parse::bankAccount);
  }

  /**
   * Your address for {@code code} on {@code network} (created on first use), e.g. ("USDT", "TRX").
   */
  public DepositAddress fetchDepositAddress(String code, String network) {
    if (network == null || network.isEmpty()) {
      throw new BadRequestException("fetchDepositAddress needs a network code, e.g. 'TRX'");
    }
    String net = network.toUpperCase(Locale.ROOT);
    Map<String, Object> body = Map.of("currency", code.toUpperCase(Locale.ROOT), "network", net);
    return Parse.depositAddress(asMap(request("private_post_wlt_address", null, null, body)), net);
  }

  /** One currency's networks with deposit/withdraw availability. */
  public List<Network> fetchCurrencyNetworks(String code) {
    return mapRows(
        list(
            "private_get_wlt_networks",
            null,
            Map.of("currency_code", code.toUpperCase(Locale.ROOT))),
        Parse::currencyNetwork);
  }

  private static String upperOrNull(String s) {
    return s == null || s.isEmpty() ? null : s.toUpperCase(Locale.ROOT);
  }

  /** Your deposits. */
  public List<Transaction> fetchDeposits() {
    return fetchDeposits(null, null, null, null);
  }

  /** Your deposits; params: {@code network}, {@code state}, {@code end}, {@code paginate}, … */
  public List<Transaction> fetchDeposits(
      String code, Long since, Integer limit, Map<String, ?> params) {
    List<Object> rows =
        paged(
            "private_get_wlt_deposits",
            params("currency", upperOrNull(code), "start", isoParam(since), "limit", limit),
            params);
    return mapRows(rows, Parse::deposit);
  }

  /** Your withdrawals. */
  public List<Transaction> fetchWithdrawals() {
    return fetchWithdrawals(null, null, null, null);
  }

  /** Your withdrawals; {@code since} is applied per day. */
  public List<Transaction> fetchWithdrawals(
      String code, Long since, Integer limit, Map<String, ?> params) {
    String start = since == null ? null : DAY.format(Instant.ofEpochMilli(since));
    List<Object> rows =
        paged(
            "private_get_wlt_withdraws",
            params("currency", upperOrNull(code), "start", start, "limit", limit),
            params);
    return mapRows(rows, Parse::withdrawal);
  }

  /**
   * Creates a withdrawal. It is sent only after {@link #verifyWithdrawOtp} (twice unless {@code
   * info.is_single_otp}). Never retried.
   *
   * <ul>
   *   <li>Crypto: {@code address} and {@code params {"network": "TRX"}}; {@code tag} is the memo.
   *   <li>IRT: {@code params {"accountNumber": id}} from {@link #fetchBankAccounts()}.
   *   <li>Internal transfer: {@code params {"alternativeAddress": phone or email}}.
   * </ul>
   */
  public Transaction withdraw(
      String code, BigDecimal amount, String address, String tag, Map<String, ?> params) {
    if (amount == null || amount.signum() <= 0) {
      throw new BadRequestException("withdraw amount must be positive");
    }
    Map<String, Object> extra = merge(null, params);
    Object network = take(extra, "network");
    Object account = take(extra, "accountNumber", "account_number");
    Object alternative = take(extra, "alternativeAddress", "alternative_address");
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("currency", code.toUpperCase(Locale.ROOT));
    body.put("amount", amount);
    if (alternative != null) {
      body.put("alternative_address", alternative);
    } else if (account != null) {
      body.put("account_number", str(account));
    } else if (address != null && !address.isEmpty()) {
      if (network == null) {
        throw new BadRequestException("crypto withdrawals need params[\"network\"]");
      }
      body.put("address", address);
      body.put("network", str(network).toUpperCase(Locale.ROOT));
      if (tag != null && !tag.isEmpty()) {
        body.put("memo", tag);
      }
    } else {
      throw new BadRequestException(
          "withdraw needs an address, params[\"accountNumber\"] or params[\"alternativeAddress\"]");
    }
    body.putAll(extra);
    return Parse.withdrawal(asMap(request("private_post_wlt_withdraws", null, null, body)));
  }

  private static Object take(Map<String, Object> m, String... keys) {
    for (String k : keys) {
      if (m.containsKey(k)) {
        return m.remove(k);
      }
    }
    return null;
  }

  /**
   * Confirms a withdrawal: first your authenticator code, then ({@code second}) the code sent to
   * you.
   */
  public Map<String, Object> verifyWithdrawOtp(String id, String otp, boolean second) {
    return asMap(
        request(
            "private_post_wlt_withdraws_verify_otp_id",
            Map.of("id", id),
            null,
            Map.of("otp", otp, "is_second_otp", second)));
  }

  /** Sends the OTP of a withdrawal in the initial state again. */
  public Map<String, Object> resendWithdrawOtp(String id, boolean first, boolean voiceCall) {
    return asMap(
        request(
            "private_post_wlt_withdraws_retry_id",
            Map.of("id", id),
            null,
            Map.of("first", first, "use_voice_call", voiceCall)));
  }

  // --- pagination ------------------------------------------------------------------------------

  private List<Object> paged(String endpointId, Map<String, ?> query, Map<String, ?> params) {
    Map<String, Object> merged = merge(query, params);
    boolean paginate = truthy(merged.remove("paginate"));
    if (paginate) {
      return allPages(endpointId, merged);
    }
    merged.remove("maxPages");
    return list(endpointId, null, merged);
  }

  /** Walks an id-cursor list: {@code offset} means "ids below this", not a row count. */
  private List<Object> allPages(String endpointId, Map<String, Object> query) {
    int maxPages = query.remove("maxPages") instanceof Number n ? n.intValue() : 100;
    if (query.get("limit") == null) {
      query.put("limit", Spec.CONSTANTS.get(MAX_PAGE_SIZE.get(endpointId)));
    }
    int limit = Integer.parseInt(str(query.get("limit")));
    List<Object> rows = new ArrayList<>();
    Long offset = null;
    for (int page = 0; page < maxPages; page++) {
      List<Object> batch = list(endpointId, null, query);
      if (batch.isEmpty()) {
        break;
      }
      long lowest = Long.MAX_VALUE;
      for (Object r : batch) {
        lowest = Math.min(lowest, idNumber(str(asMap(r).get("id"))));
      }
      if (offset != null && lowest >= offset) {
        break; // the server didn't move past the last page
      }
      rows.addAll(batch);
      if (batch.size() < limit) {
        break;
      }
      offset = lowest;
      query.put("offset", lowest);
    }
    return rows;
  }

  // --- WebSocket -------------------------------------------------------------------------------

  private BitpinWebSocket websocket() {
    wsLock.lock();
    try {
      if (ws == null) {
        ws = new BitpinWebSocket(this, cfg.wsTransport(), 1000);
      }
      return ws;
    } finally {
      wsLock.unlock();
    }
  }

  /** Waits for the next 24-hour ticker update of {@code symbol}. */
  public Ticker watchTicker(String symbol) {
    return websocket().watchTicker(symbol, null);
  }

  /**
   * Like {@link #watchTicker(String)}; throws {@link RequestTimeoutException} after {@code
   * timeout}.
   */
  public Ticker watchTicker(String symbol, Duration timeout) {
    return websocket().watchTicker(symbol, timeout);
  }

  /** Waits for the next candles of {@code timeframe} (Bitpin pushes every 10 s and on trades). */
  public List<OHLCV> watchOHLCV(String symbol, String timeframe) {
    return websocket().watchOHLCV(symbol, timeframe, null);
  }

  /** Like {@link #watchOHLCV(String, String)}, with a timeout. */
  public List<OHLCV> watchOHLCV(String symbol, String timeframe, Duration timeout) {
    return websocket().watchOHLCV(symbol, timeframe, timeout);
  }

  /** Waits for the next order-book update of {@code symbol}. */
  public OrderBook watchOrderBook(String symbol) {
    return websocket().watchOrderBook(symbol, null);
  }

  /** Like {@link #watchOrderBook(String)}, with a timeout. */
  public OrderBook watchOrderBook(String symbol, Duration timeout) {
    return websocket().watchOrderBook(symbol, timeout);
  }

  /** Waits for the next public trades of {@code symbol}. */
  public List<Trade> watchTrades(String symbol) {
    return websocket().watchTrades(symbol, null);
  }

  /** Like {@link #watchTrades(String)}, with a timeout. */
  public List<Trade> watchTrades(String symbol, Duration timeout) {
    return websocket().watchTrades(symbol, timeout);
  }

  /** Waits for the next update of one of your orders; null symbol for every market. */
  public Order watchOrders(String symbol) {
    return websocket().watchOrders(symbol, null);
  }

  /** Like {@link #watchOrders(String)}, with a timeout. */
  public Order watchOrders(String symbol, Duration timeout) {
    return websocket().watchOrders(symbol, timeout);
  }

  /** Waits for your next fill; null symbol for every market. */
  public Trade watchMyTrades(String symbol) {
    return websocket().watchMyTrades(symbol, null);
  }

  /** Like {@link #watchMyTrades(String)}, with a timeout. */
  public Trade watchMyTrades(String symbol, Duration timeout) {
    return websocket().watchMyTrades(symbol, timeout);
  }

  // --- not offered by Bitpin yet ---------------------------------------------------------------

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void cancelAllOrders() {
    throw Errors.notSupported("cancelAllOrders");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void editOrder() {
    throw Errors.notSupported("editOrder");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void fetchAccounts() {
    throw Errors.notSupported("fetchAccounts");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void fetchLedger() {
    throw Errors.notSupported("fetchLedger");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void transfer() {
    throw Errors.notSupported("transfer");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void fetchDepositWithdrawFees() {
    throw Errors.notSupported("fetchDepositWithdrawFees");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void fetchPositions() {
    throw Errors.notSupported("fetchPositions");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void setLeverage() {
    throw Errors.notSupported("setLeverage");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void createDepositAddress() {
    throw Errors.notSupported("createDepositAddress");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void watchBalance() {
    throw Errors.notSupported("watchBalance");
  }

  /** Not offered by Bitpin yet: throws {@link NotSupportedException}. */
  public void watchTickers() {
    throw Errors.notSupported("watchTickers");
  }

  /** Bitpin has no sandbox: throws {@link NotSupportedException}. */
  public void setSandboxMode(boolean enabled) {
    throw Errors.notSupported("sandbox");
  }
}
