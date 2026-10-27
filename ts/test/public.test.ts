import { describe, expect, it } from "vitest";
import { errors } from "../src/index.js";
import { NOW, setup } from "./helpers.js";

describe("market data", () => {
  it("loads and caches markets", async () => {
    const { client, mock } = setup();
    const markets = mock.endpoint("public_get_mkt_markets");
    expect(() => client.market("BTC/IRT")).toThrow(/loadMarkets/);
    expect(Object.keys(await client.loadMarkets())).toEqual(["BTC/IRT", "USDT/IRT", "ETH/USDT"]);
    await client.loadMarkets();
    expect(markets.count).toBe(1);
    expect(client.market("btc_irt").id).toBe("BTC_IRT");
    expect(client.marketsById.BTC_IRT!.symbol).toBe("BTC/IRT");
    expect(() => client.market("DOGE/IRT")).toThrow(errors.BadSymbol);
    await client.loadMarkets(true);
    expect(markets.count).toBe(2);
  });

  it("currencies, networks, suspensions", async () => {
    const { client, mock } = setup();
    mock.endpoint("public_get_mkt_currencies");
    expect((await client.fetchCurrencies()).BTC!.precision.toString()).toBe("1e-8");
    const networks = mock.endpoint("public_get_mkt_networks");
    expect((await client.fetchNetworks({ can_deposit: true })).map((n) => n.network)).toEqual([
      "BTC",
      "TRX",
    ]);
    expect(networks.last.url.searchParams.get("can_deposit")).toBe("true");
    mock.endpoint("private_get_mkt_markets_suspensions");
    expect(await client.fetchMarketSuspensions()).toEqual({ "BTC/IRT": false, "ETH/USDT": true });
  });

  it("tickers", async () => {
    const { client, mock } = setup();
    mock.endpoint("public_get_mkt_tickers");
    expect(Object.keys(await client.fetchTickers())).toEqual(["BTC/IRT", "USDT/IRT"]);
    expect(Object.keys(await client.fetchTickers(["usdt/irt"]))).toEqual(["USDT/IRT"]);
    expect((await client.fetchTicker("BTC_IRT")).last!.toString()).toBe("3145737420");
    await expect(client.fetchTicker("DOGE/IRT")).rejects.toBeInstanceOf(errors.BadSymbol);
  });

  it("order book", async () => {
    const { client, mock } = setup();
    const book = mock.endpoint("public_get_mth_orderbook_symbol");
    const result = await client.fetchOrderBook("BTC/IRT", 50);
    expect(book.last.url.pathname).toBe("/api/v1/mth/orderbook/BTC_IRT/");
    expect(book.last.url.searchParams.get("limit")).toBe("50");
    expect(result.bids[0]!.map(String)).toEqual(["3140000000", "0.05"]);
    expect(result.asks[0]!.map(String)).toEqual(["3150000000", "0.01"]);
    await client.fetchOrderBook("BTC/IRT");
    expect(book.last.url.searchParams.has("limit")).toBe(false);
    await expect(client.fetchOrderBook("BTC/IRT", 51)).rejects.toThrow(/50/);
  });

  it("trades", async () => {
    const { client, mock } = setup();
    mock.endpoint("public_get_mth_matches_symbol");
    expect((await client.fetchTrades("BTC/IRT")).map((t) => t.id)).toEqual([
      "73802970_73807080",
      "73802972_73807087",
    ]);
    expect((await client.fetchTrades("BTC/IRT", 1761550510000)).map((t) => t.id)).toEqual([
      "73802972_73807087",
    ]);
    expect((await client.fetchTrades("BTC/IRT", undefined, 1)).map((t) => t.id)).toEqual([
      "73802972_73807087",
    ]);
  });

  it("candles", async () => {
    const { client, mock } = setup();
    const candles = mock.endpoint("public_get_mkt_candles");
    const rows = await client.fetchOHLCV("BTC/IRT", "30m", 1761550200000, 2);
    const p = candles.last.url.searchParams;
    expect([p.get("symbol"), p.get("res"), p.get("from"), p.get("to")]).toEqual([
      "BTC_IRT",
      "30m",
      "1761550200",
      String(1761550200 + 3600),
    ]);
    expect(rows[0]![0]).toBe(1761550200000);
    await client.fetchOhlcv("BTC/IRT", "1h");
    expect(candles.last.url.searchParams.get("to")).toBe(String(NOW));
    expect(candles.last.url.searchParams.get("from")).toBe(String(NOW - 500 * 3600));
    expect((await client.fetchOHLCV("BTC/IRT", "30m", undefined, 1)).length).toBe(1);
    await client.fetchOHLCV("BTC/IRT");
    expect(candles.last.url.searchParams.get("res")).toBe("30m");
    await expect(client.fetchOHLCV("BTC/IRT", "2h")).rejects.toThrow(/timeframe '2h'/);
    await expect(client.fetchOHLCV("BTC/IRT", "1m", undefined, 10001)).rejects.toThrow(/10000/);
    await expect(client.fetchOHLCV("BTC/IRT", "1m", undefined, 0)).rejects.toThrow(/limit/);
  });

  it("trading fees", async () => {
    const { client, mock } = setup();
    mock.endpoint("private_get_mkt_commissions");
    expect((await client.fetchTradingFees())["BTC/IRT"]!.maker!.toString()).toBe("0.003");
    expect((await client.fetchTradingFee("USDT/IRT")).taker!.toString()).toBe("0.0015");
    await expect(client.fetchTradingFee("DOGE/IRT")).rejects.toBeInstanceOf(errors.BadSymbol);
  });

  it("describe", () => {
    const { client } = setup();
    const info = client.describe();
    expect(info.id).toBe("bitpin");
    expect(info.has.fetchOHLCV).toBe(true);
    expect(info.has.editOrder).toBe(false);
    expect(info.rateLimits.auth).toBe("3/min");
    expect(info.timeframes["30m"]).toBe("30m");
  });
});
