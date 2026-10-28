package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.TestSupport.TEST_NOW;
import static io.github.bitpindev.bitpin.TestSupport.env;
import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.bitpindev.bitpin.TestSupport.Env;
import io.github.bitpindev.bitpin.TestSupport.Reply;
import io.github.bitpindev.bitpin.TestSupport.Route;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class MarketDataTest {
  @Test
  void marketsAreLoadedOnce() {
    Env e = env();
    Route markets = e.http().endpoint("public_get_mkt_markets");
    assertThrows(BitpinException.class, () -> e.client().market("BTC/IRT"));
    Map<String, Market> got = e.client().loadMarkets();
    assertSame(got, e.client().loadMarkets());
    assertEquals(3, got.size());
    assertEquals(1, markets.count());
    assertEquals("BTC_IRT", e.client().market("btc_irt").id());
    assertThrows(BadSymbolException.class, () -> e.client().market("DOGE/IRT"));
    assertThrows(BadSymbolException.class, () -> e.client().market("bad"));
    e.client().loadMarkets(true);
    assertEquals(2, markets.count());
    assertEquals(3, e.client().fetchMarkets().size());
  }

  @Test
  void currenciesNetworksSuspensions() {
    Env e = env();
    e.http().endpoint("public_get_mkt_currencies");
    assertEquals("0.00000001", Numbers.plain(e.client().fetchCurrencies().get("BTC").precision()));
    Route nets = e.http().endpoint("public_get_mkt_networks");
    assertEquals(2, e.client().fetchNetworks(Map.of("can_deposit", true)).size());
    assertEquals("true", nets.last().query().get("can_deposit"));
    assertEquals(2, e.client().fetchNetworks().size());
    e.http().endpoint("private_get_mkt_markets_suspensions");
    assertEquals(Map.of("BTC/IRT", false, "ETH/USDT", true), e.client().fetchMarketSuspensions());
  }

  @Test
  void tickers() {
    Env e = env();
    e.http().endpoint("public_get_mkt_tickers");
    assertEquals(2, e.client().fetchTickers().size());
    assertEquals(1, e.client().fetchTickers("usdt/irt").size());
    assertEquals(1, e.client().fetchTickers(List.of("USDT_IRT")).size());
    assertEquals("3145737420", e.client().fetchTicker("BTC_IRT").last().toPlainString());
    assertThrows(BadSymbolException.class, () -> e.client().fetchTicker("DOGE/IRT"));
    assertThrows(BadSymbolException.class, () -> e.client().fetchTickers("bad"));
  }

  @Test
  void orderBookAndTrades() {
    Env e = env();
    Route book = e.http().endpoint("public_get_mth_orderbook_symbol");
    OrderBook ob = e.client().fetchOrderBook("BTC/IRT", 50);
    assertEquals("/api/v1/mth/orderbook/BTC_IRT/", book.last().path());
    assertEquals("50", book.last().query().get("limit"));
    assertEquals("3140000000", ob.bids().get(0).price().toPlainString());
    assertEquals("3150000000", ob.asks().get(0).price().toPlainString());
    e.client().fetchOrderBook("BTC/IRT");
    assertFalse(book.last().query().containsKey("limit"));
    assertThrows(BadRequestException.class, () -> e.client().fetchOrderBook("BTC/IRT", 51));
    assertThrows(BadRequestException.class, () -> e.client().fetchOrderBook("BTC/IRT", 0));

    e.http().endpoint("public_get_mth_matches_symbol");
    assertEquals(
        List.of("73802970_73807080", "73802972_73807087"), ids(e.client().fetchTrades("BTC/IRT")));
    assertEquals(
        List.of("73802972_73807087"), ids(e.client().fetchTrades("BTC/IRT", 1761550510000L, null)));
    assertEquals(List.of("73802972_73807087"), ids(e.client().fetchTrades("BTC/IRT", null, 1)));
  }

  private static List<String> ids(List<Trade> trades) {
    return trades.stream().map(Trade::id).toList();
  }

  @Test
  void candles() {
    Env e = env();
    Route candles = e.http().endpoint("public_get_mkt_candles");
    List<OHLCV> rows = e.client().fetchOHLCV("BTC/IRT", "30m", 1761550200000L, 2, null);
    Map<String, String> q = candles.last().query();
    assertEquals(
        List.of("BTC_IRT", "30m", "1761550200", String.valueOf(1761550200 + 3600)),
        List.of(q.get("symbol"), q.get("res"), q.get("from"), q.get("to")));
    assertEquals(1761550200000L, rows.get(0).timestamp());
    e.client().fetchOHLCV("BTC/IRT", "1h");
    assertEquals(String.valueOf(TEST_NOW), candles.last().query().get("to"));
    assertEquals(String.valueOf(TEST_NOW - 500 * 3600), candles.last().query().get("from"));
    assertEquals(1, e.client().fetchOHLCV("BTC/IRT", "", null, 1, null).size());
    assertEquals("30m", candles.last().query().get("res"));
    assertEquals(1, e.client().fetchOHLCV("BTC/IRT", null, 1L, 1, Map.of("extra", "x")).size());
    assertEquals("x", candles.last().query().get("extra"));
    assertThrows(BadRequestException.class, () -> e.client().fetchOHLCV("BTC/IRT", "2h"));
    assertThrows(
        BadRequestException.class, () -> e.client().fetchOHLCV("BTC/IRT", "1m", null, 10001, null));
    assertThrows(
        BadRequestException.class, () -> e.client().fetchOHLCV("BTC/IRT", "1m", null, 0, null));
  }

  @Test
  void tradingFees() {
    Env e = env();
    e.http().endpoint("private_get_mkt_commissions");
    assertEquals("0.003", e.client().fetchTradingFees().get("BTC/IRT").maker().toPlainString());
    assertEquals("0.0015", e.client().fetchTradingFee("USDT/IRT").taker().toPlainString());
    assertThrows(BadSymbolException.class, () -> e.client().fetchTradingFee("DOGE/IRT"));
  }

  @Test
  void errorsPropagateFromEveryCall() {
    Env e = env(b -> b.maxRetries(0));
    for (String id :
        List.of(
            "public_get_mkt_markets",
            "public_get_mkt_currencies",
            "public_get_mkt_networks",
            "private_get_mkt_markets_suspensions",
            "public_get_mkt_tickers",
            "public_get_mth_orderbook_symbol",
            "public_get_mth_matches_symbol",
            "public_get_mkt_candles",
            "private_get_mkt_commissions",
            "private_post_odr_orders",
            "private_post_odr_orders_bulk",
            "private_get_odr_orders_id",
            "private_get_odr_orders",
            "private_get_odr_fills",
            "private_get_odr_order_history",
            "private_get_wlt_wallets",
            "private_get_wlt_account_numbers",
            "private_post_wlt_address",
            "private_get_wlt_networks",
            "private_get_wlt_deposits",
            "private_get_wlt_withdraws",
            "private_post_wlt_withdraws")) {
      e.http().endpoint(id, Reply.of(503, null));
    }
    Bitpin c = e.client();
    List<Runnable> checks =
        List.of(
            () -> c.loadMarkets(true),
            c::fetchCurrencies,
            c::fetchNetworks,
            c::fetchMarketSuspensions,
            () -> c.fetchTicker("BTC/IRT"),
            () -> c.fetchOrderBook("BTC/IRT"),
            () -> c.fetchTrades("BTC/IRT"),
            () -> c.fetchOHLCV("BTC/IRT", "1m"),
            () -> c.fetchTradingFee("BTC/IRT"),
            () ->
                c.createOrder(
                    "BTC/IRT", "limit", "buy", java.math.BigDecimal.ONE, java.math.BigDecimal.ONE),
            () ->
                c.createOrders(
                    List.of(
                        new OrderRequest(
                            "BTC/IRT",
                            "limit",
                            "buy",
                            java.math.BigDecimal.ONE,
                            java.math.BigDecimal.ONE))),
            () -> c.fetchOrder("1"),
            c::fetchOrders,
            c::fetchMyTrades,
            c::fetchOrderHistory,
            c::fetchBalance,
            c::fetchBankAccounts,
            () -> c.fetchDepositAddress("USDT", "TRX"),
            () -> c.fetchCurrencyNetworks("USDT"),
            c::fetchDeposits,
            c::fetchWithdrawals,
            () -> c.withdraw("USDT", java.math.BigDecimal.ONE, "a", null, Map.of("network", "TRX")),
            () -> c.fetchTrades("bad"),
            () -> c.fetchOHLCV("bad", "1m"),
            () -> c.fetchOrderBook("bad"),
            () -> c.fetchTicker("bad"),
            () -> c.fetchTradingFee("bad"));
    for (int i = 0; i < checks.size(); i++) {
      int n = i;
      assertThrows(BitpinException.class, () -> checks.get(n).run(), "check " + n);
    }
  }

  @Test
  void notSupportedCoversEveryMissingCapability() {
    Bitpin c = new Bitpin();
    Map<String, Runnable> calls =
        map(
            "cancelAllOrders", (Runnable) c::cancelAllOrders,
            "editOrder", (Runnable) c::editOrder,
            "fetchAccounts", (Runnable) c::fetchAccounts,
            "fetchLedger", (Runnable) c::fetchLedger,
            "transfer", (Runnable) c::transfer,
            "fetchDepositWithdrawFees", (Runnable) c::fetchDepositWithdrawFees,
            "fetchPositions", (Runnable) c::fetchPositions,
            "setLeverage", (Runnable) c::setLeverage,
            "createDepositAddress", (Runnable) c::createDepositAddress,
            "watchBalance", (Runnable) c::watchBalance,
            "watchTickers", (Runnable) c::watchTickers,
            "sandbox", (Runnable) () -> c.setSandboxMode(true));
    c.has()
        .forEach(
            (feature, ok) -> {
              if (ok) {
                return;
              }
              Runnable call = calls.get(feature);
              assertTrue(call != null, "no method for " + feature);
              NotSupportedException e = assertThrows(NotSupportedException.class, call::run);
              assertEquals(feature, e.feature());
              assertEquals("NotSupported", e.ccxtName());
            });
  }
}
