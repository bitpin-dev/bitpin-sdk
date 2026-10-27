import { describe, expect, it } from "vitest";
import { Decimal as D } from "../src/core/numbers.js";
import * as parse from "../src/core/parse.js";
import { body } from "./helpers.js";

const T_ORDER = 1793083530123;
const d = (v: string) => new D(v);

describe("parsers (shared fixtures, same expectations as Python)", () => {
  it("times", () => {
    expect(parse.isoToMs("2026-10-27T10:15:30.123456+03:30")).toBe(T_ORDER);
    expect(parse.isoToMs("2025-10-19T11:38:27.929164Z")).toBe(1760873907929);
    expect(parse.isoToMs("2026-10-27T10:20:00.5+03:30")).toBe(1793083800500);
    expect(parse.isoToMs(null)).toBeNull();
    expect(parse.isoToMs("garbage")).toBeNull();
    expect(parse.msToIso(T_ORDER)).toBe("2026-10-27T06:45:30.123Z");
    expect(parse.msToIso(null)).toBeNull();
    expect(parse.secondsToMs(null)).toBeNull();
    expect(parse.dec("junk")).toBeNull();
  });

  it("market and currency", () => {
    const m = parse.parseMarket(body("public_get_mkt_markets")[0]);
    expect([m.id, m.symbol, m.base, m.quote, m.active, m.type]).toEqual([
      "BTC_IRT",
      "BTC/IRT",
      "BTC",
      "IRT",
      true,
      "spot",
    ]);
    expect(m.precision.amount.eq(d("1E-8"))).toBe(true);
    expect(m.precision.price.eq(1)).toBe(true);
    const suspended = parse.parseMarket(body("public_get_mkt_markets")[2]);
    expect(suspended.active).toBe(false);
    expect(suspended.precision.price.eq(d("0.01"))).toBe(true);
    const c = parse.parseCurrency(body("public_get_mkt_currencies")[1]);
    expect([c.code, c.name, c.active]).toEqual(["BTC", "Bitcoin", true]);
    expect(parse.parseCurrency({ currency: "X", precision: "0" }).name).toBe("X");
  });

  it("ticker", () => {
    const t = parse.parseTicker(body("public_get_mkt_tickers")[0]);
    expect(t.symbol).toBe("BTC/IRT");
    expect(t.last!.eq(d("3145737420"))).toBe(true);
    expect(t.percentage!.eq(d("-1.58"))).toBe(true);
    expect(t.timestamp).toBe(1761550530189);
    expect(t.datetime).toBe("2025-10-27T07:35:30.189Z");
    expect(t.baseVolume).toBeNull();
    expect(parse.parseTicker(body("public_get_mkt_tickers")[1]).high).toBeNull();
  });

  it("order book sorts sides", () => {
    const ob = parse.parseOrderBook(
      {
        asks: [
          ["3", "1"],
          ["2", "1"],
        ],
        bids: [
          ["1", "1"],
          ["1.5", "2"],
        ],
      },
      "BTC/IRT",
    );
    expect(ob.asks.map(([p]) => p.toString())).toEqual(["2", "3"]);
    expect(ob.bids.map(([p]) => p.toString())).toEqual(["1.5", "1"]);
    expect(parse.parseOrderBook({}, "X/Y").bids).toEqual([]);
  });

  it("trades and candles", () => {
    const t = parse.parseTrade(body("public_get_mth_matches_symbol")[0], "BTC/IRT");
    expect([t.id, t.side, t.amount!.toString(), t.cost!.toString(), t.timestamp]).toEqual([
      "73802972_73807087",
      "buy",
      "0.002",
      "6291474.84",
      1761550530149,
    ]);
    const mine = parse.parseMyTrade(body("private_get_odr_fills")[0]);
    expect([mine.id, mine.order, mine.symbol, mine.fee!.currency, mine.timestamp]).toEqual([
      "65375307",
      "535179300",
      "BTC/IRT",
      "IRT",
      1793083800500,
    ]);
    expect(mine.fee!.cost!.eq(11060)).toBe(true);
    const row = parse.parseOhlcv(body("public_get_mkt_candles")[0]);
    expect(row.map((v) => (v === null ? null : v.toString()))).toEqual([
      "1761550200000",
      "3100000000",
      "3120000000",
      "3090000000",
      "3110000000",
      "1.25",
    ]);
  });

  it("orders", () => {
    const o = parse.parseOrder(body("private_post_odr_orders"));
    expect([
      o.id,
      o.clientOrderId,
      o.symbol,
      o.type,
      o.side,
      o.status,
      o.timestamp,
      o.average,
      o.lastTradeTimestamp,
    ]).toEqual(["535179385", "mm-bid-1", "BTC/IRT", "limit", "buy", "open", T_ORDER, null, null]);
    expect(o.remaining!.eq(d("0.001"))).toBe(true);
    const filled = parse.parseOrder(body("private_get_odr_orders")[1]);
    expect(filled.status).toBe("closed");
    expect(filled.remaining!.isZero()).toBe(true);
    expect(filled.average!.eq(3160000000)).toBe(true);
    const oco = parse.parseOrder({
      ...body("private_post_odr_orders"),
      type: "oco",
      stop_price: "58000",
      oco_target_price: "70000",
    });
    expect([
      oco.stopPrice!.toString(),
      oco.triggerPrice!.toString(),
      oco.takeProfitPrice!.toString(),
    ]).toEqual(["58000", "58000", "70000"]);
    const hist = parse.parseHistoryOrder(body("private_get_odr_order_history").results[0]);
    expect([hist.id, hist.status, hist.timestamp, hist.lastTradeTimestamp, hist.price]).toEqual([
      "535100000",
      "closed",
      1761460000000,
      1761460000500,
      null,
    ]);
    expect(
      parse.parseHistoryOrder({
        ...body("private_get_odr_order_history").results[0],
        created_at: null,
        closed_at: null,
      }).timestamp,
    ).toBeNull();
    expect(parse.parseBulkOrders(body("private_post_odr_orders_bulk")).map((x) => x.id)).toEqual([
      "535179385",
      "535179386",
    ]);
    expect(parse.parseBulkOrders(body("private_post_odr_orders_bulk").orders).length).toBe(2);
    expect(parse.parseBulkOrders(null)).toEqual([]);
  });

  it.each([
    ["initial", "1", "0", "10", "0", "open"],
    ["active", "1", "0.5", "10", "5", "open"],
    ["closed", "1", "1", "10", "10", "closed"],
    ["closed", "1", "0.5", "10", "5", "canceled"],
    ["closed", null, "0.3", "10", "10", "closed"],
    ["closed", null, "0.3", "10", "9", "canceled"],
    ["closed", null, "0", null, "0", "closed"],
    ["weird", "1", "0", "10", "0", "weird"],
  ])("status %s base=%s → %s", (state, base, dealtBase, quote, dealtQuote, status) => {
    const raw = {
      ...body("private_post_odr_orders"),
      state,
      base_amount: base,
      dealed_base_amount: dealtBase,
      quote_amount: quote,
      dealed_quote_amount: dealtQuote,
    };
    expect(parse.parseOrder(raw).status).toBe(status);
  });

  it("balance and fees", () => {
    const b = parse.parseBalance(body("private_get_wlt_wallets"));
    expect(b.BTC.total.eq(d("0.0135"))).toBe(true);
    expect(b.free.IRT!.eq(150000000)).toBe(true);
    const summed = parse.parseBalance([
      { asset: "BTC", balance: "1", frozen: "0" },
      { asset: "BTC", balance: "2", frozen: "1" },
    ]);
    expect(summed.BTC.total.eq(4)).toBe(true);
    const f = parse.parseTradingFee(body("private_get_mkt_commissions")[0]);
    expect([f.symbol, f.maker!.toString(), f.taker!.toString(), f.percentage]).toEqual([
      "BTC/IRT",
      "0.003",
      "0.0035",
      true,
    ]);
  });

  it("wallet transactions and addresses", () => {
    const dep = parse.parseDeposit(body("private_get_wlt_deposits")[0]);
    expect([dep.id, dep.type, dep.currency, dep.status, dep.network, dep.internal]).toEqual([
      "9001",
      "deposit",
      "USDT",
      "ok",
      "TRX",
      false,
    ]);
    expect(
      parse.parseDeposit({
        ...body("private_get_wlt_deposits")[0],
        state: "waiting",
        network: "TRX",
      }).status,
    ).toBe("pending");
    const w = parse.parseWithdrawal(body("private_get_wlt_withdraws")[0]);
    expect([w.id, w.status, w.network, w.fee!.currency]).toEqual(["7001", "ok", "TRX", "USDT"]);
    const irt = parse.parseWithdrawal(body("private_get_wlt_withdraws")[1]);
    expect([irt.status, irt.address, irt.network]).toEqual(["pending", null, null]);
    expect(
      parse.parseWithdrawal({ ...body("private_get_wlt_withdraws")[0], state: "canceled" }).status,
    ).toBe("canceled");
    const a = parse.parseDepositAddress(body("private_post_wlt_address"), "TRX");
    expect([a.currency, a.network, a.tag]).toEqual(["USDT", "TRX", null]);
    const [v2, v1] = body("private_get_wlt_networks");
    expect([
      parse.parseCurrencyNetwork(v2).network,
      parse.parseCurrencyNetwork(v2).withdraw,
      parse.parseCurrencyNetwork(v2).addressPattern,
    ]).toEqual(["TRX", false, null]);
    expect(parse.parseCurrencyNetwork(v1).addressPattern).toBe("^0x[a-fA-F0-9]{40}$");
    expect(parse.parseNetwork({ code: "X" }).name).toBe("X");
    const bank = parse.parseBankAccount(body("private_get_wlt_account_numbers")[0]);
    expect([bank.id, bank.currency, bank.status]).toEqual(["123", "IRT", "verified"]);
    expect(parse.parseBankAccount({ id: 1, currency: "IRT", state: "x" }).currency).toBe("IRT");
  });
});
