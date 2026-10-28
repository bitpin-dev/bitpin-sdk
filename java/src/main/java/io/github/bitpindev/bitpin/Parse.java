package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.Json.asList;
import static io.github.bitpindev.bitpin.Json.asMap;
import static io.github.bitpindev.bitpin.Json.str;
import static io.github.bitpindev.bitpin.Json.truthy;
import static io.github.bitpindev.bitpin.Numbers.dec;
import static io.github.bitpindev.bitpin.Symbols.symbolOrRaw;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Server rows to ccxt structures. Every parser is lenient: missing fields become null or "". */
final class Parse {
  private Parse() {}

  private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
  private static final BigDecimal THOUSAND = BigDecimal.valueOf(1000);
  private static final DateTimeFormatter ISO_MS =
      DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss.SSS'Z'").withZone(ZoneOffset.UTC);

  /** Reads "2026-10-27T10:15:30.123456+03:30" or "...Z" as Unix milliseconds. */
  static Long isoToMs(Object value) {
    if (!(value instanceof String s) || s.isEmpty()) {
      return null;
    }
    try {
      return OffsetDateTime.parse(s).toInstant().toEpochMilli();
    } catch (DateTimeParseException e) {
      return null;
    }
  }

  static Long secondsToMs(Object value) {
    BigDecimal d = dec(value);
    return d == null ? null : d.multiply(THOUSAND).setScale(0, RoundingMode.FLOOR).longValue();
  }

  static String msToIso(Long ms) {
    return ms == null ? "" : ISO_MS.format(Instant.ofEpochMilli(ms));
  }

  static BigDecimal ratioToPercent(Object value) {
    BigDecimal d = dec(value);
    return d == null ? null : d.multiply(HUNDRED);
  }

  static BigDecimal tick(Object places) {
    BigDecimal n = dec(places);
    return n == null ? BigDecimal.ONE : BigDecimal.ONE.scaleByPowerOfTen(-n.intValue());
  }

  private static BigDecimal positive(BigDecimal d) {
    return d != null && d.signum() > 0 ? d : null;
  }

  private static Long ms(Object value) {
    BigDecimal d = dec(value);
    return d == null ? null : d.longValue();
  }

  static Market market(Map<String, Object> raw) {
    String base = str(raw.get("base"));
    String quote = str(raw.get("quote"));
    MinMax none = new MinMax(null, null);
    return new Market(
        str(raw.get("symbol")),
        base + "/" + quote,
        base,
        quote,
        base,
        quote,
        truthy(raw.get("tradable")) && !truthy(raw.get("suspended")),
        "spot",
        true,
        false,
        false,
        false,
        false,
        false,
        new Market.Precision(
            tick(raw.get("base_amount_precision")),
            tick(raw.get("price_precision")),
            tick(raw.get("quote_amount_precision"))),
        new Market.Limits(none, none, none),
        raw);
  }

  static Currency currency(Map<String, Object> raw) {
    String code = str(raw.get("currency"));
    String name = str(raw.get("name"));
    return new Currency(
        code,
        code,
        name.isEmpty() ? code : name,
        truthy(raw.get("tradable")),
        tick(raw.get("precision")),
        raw);
  }

  static Ticker ticker(Map<String, Object> raw) {
    Long ts = secondsToMs(raw.get("timestamp"));
    BigDecimal last = dec(raw.get("price"));
    return new Ticker(
        symbolOrRaw(raw.get("symbol")),
        ts,
        msToIso(ts),
        dec(raw.get("high")),
        dec(raw.get("low")),
        null,
        null,
        last,
        last,
        null,
        null,
        ratioToPercent(raw.get("daily_change_price")),
        dec(raw.get("mean")),
        dec(raw.get("base_volume")),
        dec(raw.get("quote_volume")),
        raw);
  }

  static List<PriceLevel> levels(Object rows, boolean descending) {
    List<PriceLevel> out = new ArrayList<>();
    for (Object row : asList(rows)) {
      List<Object> pair = asList(row);
      if (pair.size() < 2) {
        continue;
      }
      BigDecimal price = dec(pair.get(0));
      BigDecimal amount = dec(pair.get(1));
      if (price != null && amount != null) {
        out.add(new PriceLevel(price, amount));
      }
    }
    Comparator<PriceLevel> byPrice = Comparator.comparing(PriceLevel::price);
    out.sort(descending ? byPrice.reversed() : byPrice);
    return List.copyOf(out);
  }

  static OrderBook orderBook(Map<String, Object> raw, String symbol, Long ts) {
    return new OrderBook(
        symbol, levels(raw.get("bids"), true), levels(raw.get("asks"), false), ts, msToIso(ts));
  }

  static Trade trade(Map<String, Object> raw, String symbol) {
    Long ts = secondsToMs(raw.get("time"));
    return new Trade(
        str(raw.get("id")),
        "",
        symbol,
        str(raw.get("side")),
        ts,
        msToIso(ts),
        dec(raw.get("price")),
        dec(raw.get("base_amount")),
        dec(raw.get("quote_amount")),
        null,
        raw);
  }

  static Trade myTrade(Map<String, Object> raw) {
    Long ts = isoToMs(raw.get("created_at"));
    return new Trade(
        str(raw.get("id")),
        str(raw.get("order_id")),
        symbolOrRaw(raw.get("symbol")),
        str(raw.get("side")),
        ts,
        msToIso(ts),
        dec(raw.get("price")),
        dec(raw.get("base_amount")),
        dec(raw.get("quote_amount")),
        new Fee(dec(raw.get("commission")), str(raw.get("commission_currency"))),
        raw);
  }

  static OHLCV ohlcv(Map<String, Object> raw) {
    Long ts = secondsToMs(raw.get("ts"));
    return new OHLCV(
        ts == null ? 0 : ts,
        dec(raw.get("open")),
        dec(raw.get("high")),
        dec(raw.get("low")),
        dec(raw.get("close")),
        dec(raw.get("volume")));
  }

  private static BigDecimal orZero(BigDecimal d) {
    return d == null ? BigDecimal.ZERO : d;
  }

  static String orderStatus(Map<String, Object> raw) {
    String state = str(raw.get("state"));
    switch (state) {
      case "initial", "active" -> {
        return "open";
      }
      case "closed" -> {}
      default -> {
        return state;
      }
    }
    BigDecimal base = dec(raw.get("base_amount"));
    if (base != null && base.signum() > 0) {
      return orZero(dec(raw.get("dealed_base_amount"))).compareTo(base) >= 0
          ? "closed"
          : "canceled";
    }
    BigDecimal quote = dec(raw.get("quote_amount"));
    if (quote != null && quote.signum() > 0) {
      return orZero(dec(raw.get("dealed_quote_amount"))).compareTo(quote) >= 0
          ? "closed"
          : "canceled";
    }
    return "closed";
  }

  private static Order buildOrder(Map<String, Object> raw, Long ts, Long closed, String status) {
    BigDecimal amount = dec(raw.get("base_amount"));
    BigDecimal filled = dec(raw.get("dealed_base_amount"));
    BigDecimal remaining = null;
    if (amount != null) {
      remaining = filled == null ? amount : amount.subtract(filled);
      if (remaining.signum() < 0) {
        remaining = BigDecimal.ZERO;
      }
    }
    BigDecimal stop = dec(raw.get("stop_price"));
    return new Order(
        str(raw.get("id")),
        str(raw.get("identifier")),
        symbolOrRaw(raw.get("symbol")),
        str(raw.get("type")),
        str(raw.get("side")),
        status,
        ts,
        msToIso(ts),
        filled != null && filled.signum() != 0 ? closed : null,
        positive(dec(raw.get("price"))),
        stop,
        stop,
        dec(raw.get("oco_target_price")),
        positive(dec(raw.get("average_price"))),
        amount,
        dec(raw.get("dealed_quote_amount")),
        filled,
        remaining,
        new Fee(dec(raw.get("commission")), ""),
        raw);
  }

  static Order order(Map<String, Object> raw) {
    return buildOrder(
        raw, isoToMs(raw.get("created_at")), isoToMs(raw.get("closed_at")), orderStatus(raw));
  }

  /** Order-history rows are always closed and use Unix-millisecond times. */
  static Order historyOrder(Map<String, Object> raw) {
    Map<String, Object> closed = new LinkedHashMap<>(raw);
    closed.put("state", "closed");
    return buildOrder(
        raw, ms(raw.get("created_at")), ms(raw.get("closed_at")), orderStatus(closed));
  }

  /** Accepts {"orders": [...]} and a bare list. */
  static List<Order> bulkOrders(Object raw) {
    List<Object> rows = raw instanceof List<?> ? asList(raw) : asList(asMap(raw).get("orders"));
    return rows.stream().map(r -> order(asMap(r))).toList();
  }

  static Balances balance(List<Object> rows) {
    Map<String, BalanceEntry> currencies = new LinkedHashMap<>();
    Map<String, BigDecimal> free = new LinkedHashMap<>();
    Map<String, BigDecimal> used = new LinkedHashMap<>();
    Map<String, BigDecimal> total = new LinkedHashMap<>();
    List<Map<String, Object>> info = new ArrayList<>();
    for (Object item : rows) {
      Map<String, Object> row = asMap(item);
      String code = str(row.get("asset"));
      BigDecimal f = free.getOrDefault(code, BigDecimal.ZERO).add(orZero(dec(row.get("balance"))));
      BigDecimal u = used.getOrDefault(code, BigDecimal.ZERO).add(orZero(dec(row.get("frozen"))));
      free.put(code, f);
      used.put(code, u);
      total.put(code, f.add(u));
      currencies.put(code, new BalanceEntry(f, u, f.add(u)));
      info.add(row);
    }
    return new Balances(currencies, free, used, total, info);
  }

  /** Bitpin's percents (0.3 = 0.3 %) to ccxt ratios (0.003). */
  static TradingFee tradingFee(Map<String, Object> raw) {
    BigDecimal maker = dec(raw.get("maker"));
    BigDecimal taker = dec(raw.get("taker"));
    return new TradingFee(
        symbolOrRaw(raw.get("symbol")),
        maker == null ? null : maker.movePointLeft(2),
        taker == null ? null : taker.movePointLeft(2),
        true,
        true,
        raw);
  }

  private static String txStatus(Object state) {
    return switch (str(state)) {
      case "succeed" -> "ok";
      case "failed" -> "failed";
      case "canceled" -> "canceled";
      default -> "pending";
    };
  }

  private static Boolean bool(Object value) {
    return value instanceof Boolean b ? b : null;
  }

  private static String networkCode(Object value) {
    return value instanceof Map<?, ?> ? str(asMap(value).get("code")) : str(value);
  }

  static Transaction deposit(Map<String, Object> raw) {
    Long ts = isoToMs(raw.get("created_at"));
    return new Transaction(
        str(raw.get("id")),
        str(raw.get("tx_hash")),
        ts,
        msToIso(ts),
        networkCode(raw.get("network")),
        "",
        "",
        "",
        "deposit",
        dec(raw.get("amount")),
        str(raw.get("currency")),
        txStatus(raw.get("state")),
        null,
        null,
        bool(raw.get("internal")),
        str(raw.get("description")),
        raw);
  }

  static Transaction withdrawal(Map<String, Object> raw) {
    Long ts = isoToMs(raw.get("created_at"));
    Map<String, Object> crypto = asMap(raw.get("crypto_details"));
    String currency = str(raw.get("currency"));
    return new Transaction(
        str(raw.get("id")),
        str(crypto.get("tx_hash")),
        ts,
        msToIso(ts),
        str(crypto.get("network")),
        str(crypto.get("address")),
        str(crypto.get("address")),
        str(crypto.get("memo")),
        "withdrawal",
        dec(raw.get("amount")),
        currency,
        txStatus(raw.get("state")),
        isoToMs(raw.get("closed_at")),
        new Fee(dec(raw.get("commission")), currency),
        bool(raw.get("internal")),
        str(raw.get("description")),
        raw);
  }

  static DepositAddress depositAddress(Map<String, Object> raw, String network) {
    return new DepositAddress(
        str(raw.get("currency")), network, str(raw.get("address")), str(raw.get("memo")), raw);
  }

  static Network network(Map<String, Object> raw) {
    String code = str(raw.get("code"));
    String name = str(raw.get("title"));
    return new Network(
        code,
        code,
        name.isEmpty() ? code : name,
        truthy(raw.get("can_deposit")),
        truthy(raw.get("can_withdraw")),
        str(raw.get("address_pattern")),
        raw);
  }

  /** Accepts the v1 and v2 shapes of a currency-networks row. */
  static Network currencyNetwork(Map<String, Object> raw) {
    Network n = network(asMap(raw.get("network")));
    return new Network(
        n.id(),
        n.network(),
        n.name(),
        n.deposit() && !truthy(raw.get("deposit_under_maintenance")),
        n.withdraw() && !truthy(raw.get("withdraw_under_maintenance")),
        n.addressPattern(),
        raw);
  }

  static BankAccount bankAccount(Map<String, Object> raw) {
    Object currency = raw.get("currency");
    String code =
        currency instanceof Map<?, ?> ? str(asMap(currency).get("currency")) : str(currency);
    return new BankAccount(
        str(raw.get("id")),
        code,
        str(raw.get("iban")),
        str(raw.get("card")),
        str(raw.get("state")),
        raw);
  }
}
