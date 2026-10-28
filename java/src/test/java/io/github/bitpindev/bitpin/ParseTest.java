package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.Json.asList;
import static io.github.bitpindev.bitpin.Json.asMap;
import static io.github.bitpindev.bitpin.TestSupport.T_ORDER;
import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ParseTest {
  private static Map<String, Object> row(String endpointId, int i) {
    return asMap(asList(Fixtures.body(endpointId)).get(i));
  }

  private static String s(BigDecimal d) {
    return Numbers.plain(d);
  }

  @Test
  void marketsCurrenciesTickers() {
    Market m = Parse.market(row("public_get_mkt_markets", 0));
    assertEquals(List.of("BTC_IRT", "BTC/IRT", "spot"), List.of(m.id(), m.symbol(), m.type()));
    assertTrue(m.active());
    assertEquals("0.00000001", s(m.precision().amount()));
    assertEquals("1", s(m.precision().price()));
    Market sus = Parse.market(row("public_get_mkt_markets", 2));
    assertFalse(sus.active());
    assertEquals("0.01", s(sus.precision().price()));
    Currency c = Parse.currency(row("public_get_mkt_currencies", 1));
    assertEquals(
        List.of("BTC", "Bitcoin", "0.00000001"), List.of(c.code(), c.name(), s(c.precision())));
    assertEquals("X", Parse.currency(map("currency", "X")).name());
    Ticker tk = Parse.ticker(row("public_get_mkt_tickers", 0));
    assertEquals("BTC/IRT", tk.symbol());
    assertEquals("3145737420", s(tk.last()));
    assertEquals("-1.58", s(tk.percentage()));
    assertEquals(1761550530189L, tk.timestamp());
    assertEquals("2025-10-27T07:35:30.189Z", tk.datetime());
    assertNull(tk.baseVolume());
  }

  @Test
  void bookTradesCandles() {
    OrderBook ob =
        Parse.orderBook(
            map(
                "asks",
                List.of(List.of("3", "1"), List.of("2", "1"), List.of("bad")),
                "bids",
                List.of(List.of("1", "1"), List.of("1.5", "2"), List.of("x", "1"))),
            "BTC/IRT",
            null);
    assertEquals("2", s(ob.asks().get(0).price()));
    assertEquals("1.5", s(ob.bids().get(0).price()));
    assertEquals(2, ob.bids().size());
    assertEquals("", ob.datetime());
    Trade tr = Parse.trade(row("public_get_mth_matches_symbol", 0), "BTC/IRT");
    assertEquals(
        List.of("73802972_73807087", "buy", "0.002"), List.of(tr.id(), tr.side(), s(tr.amount())));
    assertEquals(1761550530149L, tr.timestamp());
    Trade mt = Parse.myTrade(row("private_get_odr_fills", 0));
    assertEquals(
        List.of("65375307", "535179300", "BTC/IRT", "IRT", "11060"),
        List.of(mt.id(), mt.order(), mt.symbol(), mt.fee().currency(), s(mt.fee().cost())));
    assertEquals(1793083800500L, mt.timestamp());
    OHLCV k = Parse.ohlcv(row("public_get_mkt_candles", 0));
    assertEquals(1761550200000L, k.timestamp());
    assertEquals(
        List.of("3100000000", "3120000000", "3090000000", "3110000000", "1.25"),
        List.of(s(k.open()), s(k.high()), s(k.low()), s(k.close()), s(k.volume())));
    assertEquals(0, Parse.ohlcv(map()).timestamp());
  }

  @Test
  void orders() {
    Order o = Parse.order(asMap(Fixtures.body("private_post_odr_orders")));
    assertEquals(
        List.of("535179385", "mm-bid-1", "BTC/IRT", "limit", "open", "0.001"),
        List.of(o.id(), o.clientOrderId(), o.symbol(), o.type(), o.status(), s(o.remaining())));
    assertEquals(T_ORDER, o.timestamp());
    assertNull(o.average());
    assertNull(o.lastTradeTimestamp());
    Order filled = Parse.order(row("private_get_odr_orders", 1));
    assertEquals(
        List.of("closed", "0", "3160000000"),
        List.of(filled.status(), s(filled.remaining()), s(filled.average())));
    Order h =
        Parse.historyOrder(
            asMap(
                asList(asMap(Fixtures.body("private_get_odr_order_history")).get("results"))
                    .get(0)));
    assertEquals("closed", h.status());
    assertEquals(1761460000000L, h.timestamp());
    assertEquals(1761460000500L, h.lastTradeTimestamp());
    assertNull(h.price());
    assertEquals(2, Parse.bulkOrders(Fixtures.body("private_post_odr_orders_bulk")).size());
    assertEquals(
        2,
        Parse.bulkOrders(asMap(Fixtures.body("private_post_odr_orders_bulk")).get("orders"))
            .size());
    assertNull(Parse.order(map("id", "1", "symbol", "A_B", "state", "active")).remaining());
    Order over = Parse.order(map("base_amount", "1", "dealed_base_amount", "2", "state", "closed"));
    assertEquals("0", s(over.remaining()));

    Map<String, Object> base = asMap(Fixtures.body("private_post_odr_orders"));
    String[][] cases = {
      {"initial", "1", "0", "10", "0", "open"},
      {"closed", "1", "1", "10", "10", "closed"},
      {"closed", "1", "0.5", "10", "5", "canceled"},
      {"closed", "", "0.3", "10", "10", "closed"},
      {"closed", "", "0.3", "10", "9", "canceled"},
      {"closed", "", "0", "", "0", "closed"},
      {"weird", "1", "0", "10", "0", "weird"},
    };
    for (String[] c : cases) {
      Map<String, Object> raw = new LinkedHashMap<>(base);
      raw.put("state", c[0]);
      raw.put("base_amount", c[1]);
      raw.put("dealed_base_amount", c[2]);
      raw.put("quote_amount", c[3]);
      raw.put("dealed_quote_amount", c[4]);
      assertEquals(c[5], Parse.order(raw).status(), String.join(",", c));
    }
  }

  @Test
  void walletRows() {
    Balances bal = Parse.balance(asList(Fixtures.body("private_get_wlt_wallets")));
    assertEquals("0.0135", s(bal.currencies().get("BTC").total()));
    assertEquals("150000000", s(bal.free().get("IRT")));
    Balances sum =
        Parse.balance(
            List.of(
                map("asset", "BTC", "balance", "1"),
                map("asset", "BTC", "balance", "2", "frozen", "1")));
    assertEquals("4", s(sum.total().get("BTC")));
    assertEquals(2, sum.info().size());
    TradingFee fee = Parse.tradingFee(row("private_get_mkt_commissions", 0));
    assertEquals(List.of("0.003", "0.0035"), List.of(s(fee.maker()), s(fee.taker())));
    assertTrue(fee.percentage() && fee.tierBased());
    assertNull(Parse.tradingFee(map("symbol", "A_B")).maker());
    Transaction dep = Parse.deposit(row("private_get_wlt_deposits", 0));
    assertEquals(
        List.of("9001", "ok", "TRX", "deposit"),
        List.of(dep.id(), dep.status(), dep.network(), dep.type()));
    assertFalse(dep.internal());
    assertEquals(
        "pending", Parse.deposit(map("id", "1", "state", "waiting", "network", "TRX")).status());
    assertNull(Parse.deposit(map("internal", "no")).internal());
    Transaction w = Parse.withdrawal(row("private_get_wlt_withdraws", 0));
    assertEquals(
        List.of("7001", "ok", "TRX", "USDT"),
        List.of(w.id(), w.status(), w.network(), w.fee().currency()));
    assertEquals("", Parse.withdrawal(row("private_get_wlt_withdraws", 1)).address());
    assertEquals("failed", Parse.withdrawal(map("state", "failed")).status());
    assertEquals("canceled", Parse.withdrawal(map("state", "canceled")).status());
    DepositAddress a =
        Parse.depositAddress(asMap(Fixtures.body("private_post_wlt_address")), "TRX");
    assertEquals(List.of("USDT", "TRX", ""), List.of(a.currency(), a.network(), a.tag()));
    List<Object> nets = asList(Fixtures.body("private_get_wlt_networks"));
    Network v2 = Parse.currencyNetwork(asMap(nets.get(0)));
    Network v1 = Parse.currencyNetwork(asMap(nets.get(1)));
    assertEquals("TRX", v2.network());
    assertFalse(v2.withdraw());
    assertEquals("", v2.addressPattern());
    assertEquals("^0x[a-fA-F0-9]{40}$", v1.addressPattern());
    assertEquals("X", Parse.network(map("code", "X")).name());
    BankAccount bank = Parse.bankAccount(row("private_get_wlt_account_numbers", 0));
    assertEquals(
        List.of("123", "IRT", "verified"), List.of(bank.id(), bank.currency(), bank.status()));
    assertEquals("IRT", Parse.bankAccount(map("id", 1.0, "currency", "IRT")).currency());
  }

  @Test
  void times() {
    assertNull(Parse.isoToMs("garbage"));
    assertNull(Parse.isoToMs(""));
    assertNull(Parse.isoToMs(5));
    assertEquals(1793083800500L, Parse.isoToMs("2026-10-27T10:20:00.5+03:30"));
    assertEquals(1760873907929L, Parse.isoToMs("2025-10-19T11:38:27.929164Z"));
    assertNull(Parse.secondsToMs(null));
    assertEquals("1", s(Parse.tick(null)));
    assertNull(Parse.ratioToPercent(null));
  }
}
