package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.TestSupport.TEST_NOW;
import static io.github.bitpindev.bitpin.TestSupport.T_ORDER;
import static io.github.bitpindev.bitpin.TestSupport.env;
import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.bitpindev.bitpin.TestSupport.Env;
import io.github.bitpindev.bitpin.TestSupport.Reply;
import io.github.bitpindev.bitpin.TestSupport.Route;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class OrdersTest {
  private static BigDecimal d(String s) {
    return new BigDecimal(s);
  }

  @Test
  void createOrderBuildsTheBody() {
    Env e = env();
    Route orders = e.http().endpoint("private_post_odr_orders");
    Order o =
        e.client()
            .createOrder(
                "BTC/IRT",
                "limit",
                "buy",
                d("0.001"),
                d("3100000000"),
                Map.of("clientOrderId", "mm-bid-1"));
    assertEquals(
        map(
            "symbol",
            "BTC_IRT",
            "type",
            "limit",
            "side",
            "buy",
            "base_amount",
            "0.001",
            "price",
            "3100000000",
            "identifier",
            "mm-bid-1"),
        orders.last().body());
    assertEquals(List.of("535179385", "open"), List.of(o.id(), o.status()));
    e.client()
        .createOrder("USDT/IRT", "market", "buy", null, d("5"), Map.of("quoteAmount", "1000000"));
    assertEquals(
        map("symbol", "USDT_IRT", "type", "market", "side", "buy", "quote_amount", "1000000"),
        orders.last().body());
    e.client()
        .createOrder(
            "BTC/USDT",
            "oco",
            "sell",
            d("1"),
            d("57990"),
            Map.of("triggerPrice", 58000, "takeProfitPrice", 70000));
    assertEquals(
        map(
            "symbol",
            "BTC_USDT",
            "type",
            "oco",
            "side",
            "sell",
            "base_amount",
            "1",
            "price",
            "57990",
            "stop_price",
            "58000",
            "oco_target_price",
            "70000"),
        orders.last().body());
    e.client().createOrder("BTC/IRT", "limit", "sell", d("1.50"), d("1E+3"));
    assertEquals("1.5", ((Map<?, ?>) orders.last().body()).get("base_amount"));
    assertEquals("1000", ((Map<?, ?>) orders.last().body()).get("price"));
  }

  record Bad(
      String sym,
      String type,
      String side,
      BigDecimal amount,
      BigDecimal price,
      Map<String, ?> params,
      String msg) {}

  @Test
  void createOrderValidatesLocally() {
    Env e = env();
    Route orders = e.http().endpoint("private_post_odr_orders");
    BigDecimal one = BigDecimal.ONE;
    List<Bad> cases =
        List.of(
            new Bad("BTC/IRT", "limit", "buy", null, one, null, "amount"),
            new Bad("BTC/IRT", "limit", "buy", one, null, null, "price"),
            new Bad("BTC/IRT", "market", "buy", null, null, null, "amount or params"),
            new Bad("BTC/IRT", "market", "buy", one, null, Map.of("quoteAmount", 10), "only one"),
            new Bad("BTC/IRT", "stop_limit", "buy", one, one, null, "stopPrice"),
            new Bad("BTC/IRT", "oco", "buy", one, one, Map.of("stopPrice", 1), "takeProfitPrice"),
            new Bad("BTC/IRT", "trailing", "buy", one, one, null, "type"),
            new Bad("BTC/IRT", "limit", "long", one, one, null, "side"),
            new Bad("BTC/IRT", "limit", "buy", BigDecimal.ZERO, one, null, "amount"),
            new Bad("BTC/IRT", "limit", "buy", one, d("-5"), null, "price"),
            new Bad(
                "BTC/IRT",
                "stop_limit",
                "buy",
                one,
                one,
                Map.of("stopPrice", 1, "triggerPrice", 2),
                "twice"),
            new Bad(
                "BTC/IRT", "stop_limit", "buy", one, one, Map.of("stopPrice", "abc"), "stopPrice"),
            new Bad("BTC-IRT", "limit", "buy", one, one, null, "invalid symbol"));
    int before = orders.count();
    for (Bad b : cases) {
      BitpinException ex =
          assertThrows(
              BitpinException.class,
              () -> e.client().createOrder(b.sym, b.type, b.side, b.amount, b.price, b.params),
              b.msg);
      assertTrue(ex.getMessage().contains(b.msg), b + ": " + ex.getMessage());
    }
    assertEquals(before, orders.count());
    // the same value under both names is fine
    e.client()
        .createOrder(
            "BTC/IRT", "stop_limit", "buy", one, one, Map.of("stopPrice", 1, "triggerPrice", 1));
    e.http()
        .endpoint("private_post_odr_orders", Reply.of(406, map("detail", "insufficent_balance")));
    assertThrows(
        InsufficientFundsException.class,
        () -> e.client().createOrder("BTC/IRT", "limit", "buy", one, one));
  }

  @Test
  void createOrdersInBulk() {
    Env e = env();
    Route bulk = e.http().endpoint("private_post_odr_orders_bulk");
    List<Order> created =
        e.client()
            .createOrders(
                List.of(
                    new OrderRequest(
                        "BTC/IRT",
                        "limit",
                        "buy",
                        d("0.001"),
                        d("3100000000"),
                        Map.of("clientOrderId", "a")),
                    new OrderRequest("BTC/IRT", "limit", "buy", d("0.001"), d("3090000000"))));
    assertEquals(2, created.size());
    assertEquals(
        List.of(
            map(
                "symbol",
                "BTC_IRT",
                "type",
                "limit",
                "side",
                "buy",
                "base_amount",
                "0.001",
                "price",
                "3100000000",
                "identifier",
                "a"),
            map(
                "symbol",
                "BTC_IRT",
                "type",
                "limit",
                "side",
                "buy",
                "base_amount",
                "0.001",
                "price",
                "3090000000")),
        bulk.last().body());
    OrderRequest one = new OrderRequest("BTC/IRT", "limit", "buy", BigDecimal.ONE, BigDecimal.ONE);
    assertThrows(BadRequestException.class, () -> e.client().createOrders(List.of()));
    assertThrows(BadRequestException.class, () -> e.client().createOrders(null));
    assertThrows(
        BadRequestException.class, () -> e.client().createOrders(Collections.nCopies(11, one)));
    assertThrows(
        InvalidOrderException.class,
        () ->
            e.client().createOrders(List.of(new OrderRequest("BTC/IRT", "x", "buy", null, null))));
  }

  @Test
  void fetchOrders() {
    Env e = env();
    e.http().endpoint("private_get_odr_orders_id");
    assertEquals("mm-bid-1", e.client().fetchOrder("535179385").clientOrderId());
    e.http().endpoint("private_get_odr_orders_id", Reply.of(404, map("detail", "Not found.")));
    assertThrows(OrderNotFoundException.class, () -> e.client().fetchOrder("1"));

    Route list = e.http().endpoint("private_get_odr_orders");
    List<Order> got = e.client().fetchOrders("BTC/IRT", T_ORDER, 2, Map.of("side", "buy"));
    Map<String, String> q = list.last().query();
    assertEquals(
        List.of("BTC_IRT", "2", "buy", "2026-10-27T06:45:30.123+00:00"),
        List.of(q.get("symbol"), q.get("limit"), q.get("side"), q.get("start")));
    assertEquals(List.of("535179300", "535179385"), List.of(got.get(0).id(), got.get(1).id()));
    e.client().fetchOrders("BTC/IRT");
    e.client().fetchOpenOrders();
    assertEquals("initial,active", list.last().query().get("state"));
    e.client().fetchOpenOrders("BTC/IRT");
    e.client().fetchClosedOrders();
    assertEquals("closed", list.last().query().get("state"));
    e.client().fetchClosedOrders("BTC/IRT");
    assertThrows(BadSymbolException.class, () -> e.client().fetchOrders("bad"));
  }

  static Reply orderPage(int... ids) {
    Map<String, Object> base = Json.asMap(Fixtures.body("private_post_odr_orders"));
    List<Object> rows = new ArrayList<>();
    for (int id : ids) {
      Map<String, Object> row = new LinkedHashMap<>(base);
      row.put("id", String.valueOf(id));
      rows.add(row);
    }
    return Reply.of(200, rows);
  }

  @Test
  void paginationFollowsIdCursors() {
    Env e = env();
    Route r = e.http().on("GET", "/api/v1/odr/orders/", orderPage(30, 20), orderPage(10));
    assertEquals(3, e.client().fetchOrders(null, null, 2, Map.of("paginate", true)).size());
    assertEquals("20", r.at(1).query().get("offset"));

    int[] full = new int[250];
    for (int i = 0; i < full.length; i++) {
      full[i] = 1000 + i;
    }
    Route open = e.http().on("GET", "/api/v1/odr/orders/", orderPage(full), orderPage(5));
    assertEquals(
        251, e.client().fetchOpenOrders(null, null, null, Map.of("paginate", true)).size());
    assertEquals("250", open.at(0).query().get("limit"));

    Route stuck = e.http().on("GET", "/api/v1/odr/orders/", orderPage(2, 1));
    assertEquals(2, e.client().fetchOrders(null, null, 2, Map.of("paginate", true)).size());
    assertEquals(2, stuck.count());

    Route pages =
        e.http()
            .on(
                "GET",
                "/api/v1/odr/orders/",
                orderPage(92, 91),
                orderPage(82, 81),
                orderPage(72, 71),
                orderPage(62, 61));
    e.client().fetchOrders(null, null, 2, Map.of("paginate", true, "maxPages", 3));
    assertEquals(3, pages.count());

    Route empty = e.http().on("GET", "/api/v1/odr/orders/", orderPage());
    assertEquals(0, e.client().fetchOrders(null, null, null, Map.of("paginate", true)).size());
    assertEquals(1, empty.count());

    Route plain = e.http().on("GET", "/api/v1/odr/orders/", orderPage(1));
    e.client().fetchOrders(null, null, null, Map.of("paginate", false, "maxPages", 3));
    assertEquals(Map.of(), plain.last().query());

    e.http().on("GET", "/api/v1/odr/orders/", Reply.of(503, null));
    assertThrows(
        NetworkException.class,
        () -> e.client().fetchOrders(null, null, null, Map.of("paginate", true)));
  }

  @Test
  void cancels() {
    Env e = env();
    Route c = e.http().endpoint("private_delete_odr_orders_id");
    e.client().cancelOrder("7");
    assertEquals("/api/v1/odr/orders/7/", c.last().path());
    Route byId = e.http().endpoint("private_delete_odr_orders_identifier_identifier");
    e.client().cancelOrderByIdentifier("mm-bid-1");
    assertEquals("/api/v1/odr/orders/identifier/mm-bid-1/", byId.last().path());
    e.http()
        .endpoint(
            "private_delete_odr_orders_id", Reply.of(406, map("code", "cancel_order_not_allowed")));
    assertThrows(InvalidOrderException.class, () -> e.client().cancelOrder("7"));

    Route bulk = e.http().endpoint("private_delete_odr_orders_bulk");
    CancelResult res = e.client().cancelOrders(List.of("535179385", "535179386"), null);
    assertEquals(map("ids", List.of("535179385", "535179386")), bulk.last().body());
    assertEquals(List.of("535179385"), res.canceled());
    assertEquals(List.of("535179386"), res.notCanceled());
    e.client().cancelOrders(null, List.of("a"));
    assertEquals(map("identifiers", List.of("a")), bulk.last().body());
    assertThrows(BadRequestException.class, () -> e.client().cancelOrders(null, null));
    assertThrows(BadRequestException.class, () -> e.client().cancelOrders(List.of(), List.of()));
    assertThrows(
        BadRequestException.class, () -> e.client().cancelOrders(List.of("1"), List.of("a")));
    assertThrows(
        BadRequestException.class,
        () -> e.client().cancelOrders(Collections.nCopies(11, "1"), null));
    e.http().endpoint("private_delete_odr_orders_bulk", Reply.of(503, null));
    assertThrows(BitpinException.class, () -> e.client().cancelOrders(List.of("1"), null));

    Env both = env(b -> b.rateLimit("order_bulk_cancel", "1/hour"));
    both.http().endpoint("private_post_odr_orders_bulk");
    both.http().endpoint("private_delete_odr_orders_bulk");
    both.client()
        .createOrders(
            List.of(new OrderRequest("BTC/IRT", "limit", "buy", BigDecimal.ONE, BigDecimal.ONE)));
    both.client().cancelOrders(List.of("1"), null);
    assertEquals(List.of(3600.0), both.time().slept());
  }

  @Test
  void fills() {
    Env e = env();
    Route fills = e.http().endpoint("private_get_odr_fills");
    long since = TEST_NOW * 1000 - 3_600_000;
    List<Trade> trades = e.client().fetchMyTrades("BTC/IRT", since, 100, null);
    assertEquals(
        List.of(String.valueOf(since / 1000), "100", "IRT"),
        List.of(
            fills.last().query().get("start"),
            fills.last().query().get("limit"),
            trades.get(0).fee().currency()));
    assertThrows(
        BadRequestException.class,
        () -> e.client().fetchMyTrades(null, TEST_NOW * 1000 - 86_401_000, null, null));
    Map<String, Object> fill =
        Json.asMap(Json.asList(Fixtures.body("private_get_odr_fills")).get(0));
    Map<String, Object> a = new LinkedHashMap<>(fill);
    a.put("id", "3");
    Map<String, Object> b = new LinkedHashMap<>(fill);
    b.put("id", "1");
    e.http().endpoint("private_get_odr_fills", Reply.of(200, List.of(a, b)));
    List<Trade> got = e.client().fetchMyTrades();
    assertEquals(List.of("1", "3"), List.of(got.get(0).id(), got.get(1).id()));
    e.client().fetchMyTrades("BTC/IRT");
    assertThrows(BadSymbolException.class, () -> e.client().fetchMyTrades("bad"));
  }

  @Test
  void orderHistoryFollowsTheCursor() {
    Env e = env();
    Map<String, Object> row =
        Json.asMap(
            Json.asList(Json.asMap(Fixtures.body("private_get_odr_order_history")).get("results"))
                .get(0));
    Map<String, Object> second = new LinkedHashMap<>(row);
    second.put("id", "2");
    Route h =
        e.http()
            .on(
                "GET",
                "/api/v1/odr/order_history/",
                Reply.of(200, map("results", List.of(row), "next_cursor", "c1", "has_next", true)),
                Reply.of(
                    200, map("results", List.of(second), "next_cursor", "", "has_next", false)));
    List<Order> res =
        e.client()
            .fetchOrderHistory(
                "BTC/IRT", 1L, 2L, 1, Map.of("side", "buy", "type", "market", "paginate", true));
    assertEquals(
        Map.of(
            "symbol", "BTC_IRT", "start", "1", "end", "2", "limit", "1", "side", "buy", "type",
            "market"),
        h.at(0).query());
    assertEquals(
        Map.of("symbol", "BTC_IRT", "limit", "1", "side", "buy", "type", "market", "cursor", "c1"),
        h.at(1).query());
    assertEquals(List.of("535100000", "2"), List.of(res.get(0).id(), res.get(1).id()));

    Route same =
        e.http()
            .on(
                "GET",
                "/api/v1/odr/order_history/",
                Reply.of(
                    200, map("results", List.of(row), "next_cursor", "same", "has_next", true)));
    assertEquals(
        1, e.client().fetchOrderHistory(null, null, null, null, Map.of("paginate", true)).size());
    assertEquals(2, same.count());
    e.client().fetchOrderHistory();
    assertEquals(3, same.count());

    assertThrows(
        BadRequestException.class, () -> e.client().fetchOrderHistory(null, null, null, 201, null));
    assertThrows(
        BadRequestException.class, () -> e.client().fetchOrderHistory(null, null, null, 0, null));
    assertThrows(
        BadRequestException.class,
        () -> e.client().fetchOrderHistory(null, 1L, 91L * 86_400_000, null, null));
    assertThrows(
        BadRequestException.class, () -> e.client().fetchOrderHistory(null, 5L, 5L, null, null));
    assertThrows(
        BadSymbolException.class,
        () -> e.client().fetchOrderHistory("bad", null, null, null, null));
  }
}
