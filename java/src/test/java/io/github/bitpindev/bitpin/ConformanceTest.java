package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.Json.asList;
import static io.github.bitpindev.bitpin.Json.asMap;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

import java.lang.reflect.RecordComponent;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.function.BiFunction;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

/**
 * Every SDK must parse the shared fixtures into the same result as the Python reference
 * (fixtures/expected.json, written by scripts/gen_expected.py).
 */
class ConformanceTest {
  private static final Map<String, BiFunction<Object, List<Object>, Object>> PARSERS =
      Map.ofEntries(
          Map.entry("parse_market", (r, a) -> Parse.market(asMap(r))),
          Map.entry("parse_currency", (r, a) -> Parse.currency(asMap(r))),
          Map.entry("parse_ticker", (r, a) -> Parse.ticker(asMap(r))),
          Map.entry(
              "parse_order_book", (r, a) -> Parse.orderBook(asMap(r), (String) a.get(0), null)),
          Map.entry("parse_trade", (r, a) -> Parse.trade(asMap(r), (String) a.get(0))),
          Map.entry("parse_my_trade", (r, a) -> Parse.myTrade(asMap(r))),
          Map.entry("parse_ohlcv", (r, a) -> Parse.ohlcv(asMap(r))),
          Map.entry("parse_order", (r, a) -> Parse.order(asMap(r))),
          Map.entry("parse_history_order", (r, a) -> Parse.historyOrder(asMap(r))),
          Map.entry("parse_bulk_orders", (r, a) -> Parse.bulkOrders(r)),
          Map.entry("parse_balance", (r, a) -> Parse.balance(asList(r))),
          Map.entry("parse_trading_fee", (r, a) -> Parse.tradingFee(asMap(r))),
          Map.entry("parse_deposit", (r, a) -> Parse.deposit(asMap(r))),
          Map.entry("parse_withdrawal", (r, a) -> Parse.withdrawal(asMap(r))),
          Map.entry(
              "parse_deposit_address", (r, a) -> Parse.depositAddress(asMap(r), (String) a.get(0))),
          Map.entry("parse_currency_network", (r, a) -> Parse.currencyNetwork(asMap(r))),
          Map.entry("parse_network", (r, a) -> Parse.network(asMap(r))),
          Map.entry("parse_bank_account", (r, a) -> Parse.bankAccount(asMap(r))));

  private static final Set<String> SEEN = new HashSet<>();

  /** Java results in the reference's JSON shape. */
  static Object shape(Object value) {
    return switch (value) {
      case null -> null;
      case BigDecimal d -> Numbers.plain(d);
      case PriceLevel l -> List.of(Numbers.plain(l.price()), Numbers.plain(l.amount()));
      case OHLCV c ->
          Stream.of(c.timestamp(), c.open(), c.high(), c.low(), c.close(), c.volume())
              .map(ConformanceTest::shape)
              .toList();
      case Balances b -> {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("free", shape(b.free()));
        out.put("used", shape(b.used()));
        out.put("total", shape(b.total()));
        b.currencies().forEach((code, e) -> out.put(code, shape(e)));
        yield out;
      }
      case Record r -> {
        Map<String, Object> out = new LinkedHashMap<>();
        for (RecordComponent c : r.getClass().getRecordComponents()) {
          try {
            out.put(c.getName(), shape(c.getAccessor().invoke(r)));
          } catch (ReflectiveOperationException e) {
            throw new AssertionError(e);
          }
        }
        yield out;
      }
      case Map<?, ?> m -> {
        Map<String, Object> out = new LinkedHashMap<>();
        m.forEach((k, v) -> out.put(String.valueOf(k), shape(v)));
        yield out;
      }
      case List<?> l -> l.stream().map(ConformanceTest::shape).toList();
      default -> value;
    };
  }

  private static String normKey(String key) {
    return key.replace("_", "").toLowerCase(Locale.ROOT);
  }

  private static boolean isEmpty(Object value) {
    return value == null
        || (value instanceof String s && s.isEmpty())
        || (value instanceof List<?> l && l.isEmpty());
  }

  private static String text(Object value) {
    return value instanceof BigDecimal d ? Numbers.plain(d) : String.valueOf(value);
  }

  static void compare(Object want, Object got, String path, List<String> problems) {
    if (isEmpty(want)) {
      if (!isEmpty(got)) {
        problems.add(path + ": expected empty, got " + got);
      }
      return;
    }
    if (want instanceof List<?> w) {
      if (!(got instanceof List<?> g) || g.size() != w.size()) {
        problems.add(path + ": expected " + w.size() + " items, got " + got);
        return;
      }
      for (int i = 0; i < w.size(); i++) {
        compare(w.get(i), g.get(i), path + "[" + i + "]", problems);
      }
    } else if (want instanceof Map<?, ?> w) {
      Map<String, Object> actual = new LinkedHashMap<>();
      if (got instanceof Map<?, ?> g) {
        g.forEach(
            (k, v) -> {
              if (!normKey(String.valueOf(k)).equals("info")) {
                actual.put(normKey(String.valueOf(k)), v);
              }
            });
      }
      for (Object k : new TreeSet<>(w.keySet())) {
        compare(w.get(k), actual.get(normKey(String.valueOf(k))), path + "." + k, problems);
      }
    } else if (!text(want).equals(text(got))) {
      problems.add(path + ": expected " + want + ", got " + got);
    }
  }

  @TestFactory
  Stream<DynamicTest> parsersMatchThePythonReference() {
    Map<String, Object> cases = asMap(Json.parse(Fixtures.read("expected.json")));
    return cases.entrySet().stream()
        .map(
            entry ->
                DynamicTest.dynamicTest(
                    entry.getKey(),
                    () -> {
                      Map<String, Object> c = asMap(entry.getValue());
                      String parser = (String) c.get("parser");
                      BiFunction<Object, List<Object>, Object> fn = PARSERS.get(parser);
                      if (fn == null) {
                        fail("no Java parser for " + parser);
                      }
                      SEEN.add(parser);
                      Object row = Fixtures.body((String) c.get("fixture"));
                      for (Object step : asList(c.get("path"))) {
                        row =
                            step instanceof Number n
                                ? asList(row).get(n.intValue())
                                : asMap(row).get(step);
                      }
                      List<String> problems = new ArrayList<>();
                      compare(
                          c.get("output"),
                          shape(fn.apply(row, asList(c.get("args")))),
                          "$",
                          problems);
                      assertTrue(problems.isEmpty(), String.join("\n", problems));
                    }));
  }

  @AfterAll
  static void everyParserIsCovered() {
    assertEquals(PARSERS.keySet(), SEEN, "expected.json must cover every parser");
  }
}
