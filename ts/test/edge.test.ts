// Edge cases: sparse server payloads, printing, and helpers' less common branches.
import { inspect } from "node:util";
import { describe, expect, it } from "vitest";
import { resolveConfig } from "../src/config.js";
import { mapError } from "../src/core/errors.js";
import * as parse from "../src/core/parse.js";
import { insertSorted } from "../src/core/ratelimit.js";
import { buildRequest } from "../src/core/request.js";
import type { errors } from "../src/index.js";
import * as ws from "../src/ws/parse.js";
import { body, setup } from "./helpers.js";

describe("edge cases", () => {
  it("prints the config without secrets", () => {
    const config = resolveConfig({ apiKey: "AKEY", secretKey: "SKEY" });
    const text = inspect(config);
    expect(text).toContain("***");
    expect(text).not.toContain("SKEY");
    expect(resolveConfig({}).toString()).toContain('"apiKey":null');
  });

  it("sorted insert keeps order for earlier values", () => {
    const list = [1, 5, 9];
    insertSorted(list, 3);
    insertSorted(list, 9);
    insertSorted(list, 0);
    expect(list).toEqual([0, 1, 3, 5, 9, 9]);
  });

  it("query values pass strings and Decimals through", () => {
    const req = buildRequest(
      resolveConfig({}),
      "public_get_mkt_networks",
      {},
      { code: "TRX", n: 1.5 },
    );
    expect(req.params).toEqual({ code: "TRX", n: "1.5" });
  });

  it("error helpers on odd bodies", () => {
    expect(mapError("x", 418, ["a", "b"]).message).toBe('418 x: ["a","b"]');
    expect(mapError("x", 418, { detail: 5 }).message).toBe('418 x: {"detail":5}');
    expect(
      (mapError("x", 429, { detail: "slow down" }, "") as errors.RateLimitExceeded).retryAfter,
    ).toBeNull();
  });

  it("parsers tolerate sparse rows", () => {
    expect(
      parse.parseMarket({ symbol: "A_B", base: "A", quote: "B" }).precision.price.toString(),
    ).toBe("1");
    expect(parse.parseTicker({ symbol: "A_B" }).timestamp).toBeNull();
    expect(parse.parseMyTrade({ id: 1, symbol: "A_B" }).fee).toEqual({
      cost: null,
      currency: null,
    });
    const order = parse.parseOrder({ id: 1, symbol: "A_B", state: "active" });
    expect([order.amount, order.remaining, order.filled, order.lastTradeTimestamp]).toEqual([
      null,
      null,
      null,
      null,
    ]);
    expect(parse.parseBalance([{ asset: "A" }]).A.total.toString()).toBe("0");
    expect(parse.parseTradingFee({ symbol: "A_B" })).toMatchObject({ maker: null, taker: null });
    expect(parse.parseDeposit({ id: 1, network: null }).network).toBeNull();
    expect(parse.parseWithdrawal({ id: 1, crypto_details: { memo: "m" } }).tag).toBe("m");
    expect(parse.parseCurrencyNetwork({}).network).toBe("undefined");
    expect(parse.parseBankAccount({ id: 1, currency: { currency: "" } }).currency).toBeNull();
    expect(parse.parseBulkOrders({}).length).toBe(0);
  });

  it("ws parsers tolerate sparse messages", () => {
    expect(ws.parseWsTicker({ symbol: "A_B" }).timestamp).toBeNull();
    expect(ws.parseWsOhlcv({}, "1m")).toEqual([]);
    expect(ws.parseWsTrades({ symbol: "A_B" })).toEqual([]);
    expect(ws.parseWsOrderBook({ symbol: "A_B" }).timestamp).toBeNull();
  });

  it("sorts fills and orders with equal times by id", async () => {
    const { client, mock } = setup();
    const fill = body("private_get_odr_fills")[0];
    mock.endpoint("private_get_odr_fills", {
      body: [
        { ...fill, id: 3 },
        { ...fill, id: 1 },
        { ...fill, id: 2, created_at: null },
      ],
    });
    expect((await client.fetchMyTrades()).map((t) => t.id)).toEqual(["2", "1", "3"]);
    const order = body("private_post_odr_orders");
    mock.endpoint("private_get_odr_orders", {
      body: [
        { ...order, id: 9 },
        { ...order, id: 4 },
        { ...order, id: 5, created_at: null },
      ],
    });
    expect((await client.fetchOrders()).map((o) => o.id)).toEqual(["5", "4", "9"]);
    mock.endpoint("public_get_mth_matches_symbol", {
      body: [
        { id: "b", side: "buy" },
        { id: "a", side: "buy", time: 1 },
      ],
    });
    expect((await client.fetchTrades("A/B")).map((t) => t.id)).toEqual(["b", "a"]);
  });
});
