import { describe, expect, it } from "vitest";
import { Decimal, errors } from "../src/index.js";
import { body, NOW, setup } from "./helpers.js";

const order = body("private_post_odr_orders");

describe("orders", () => {
  it("creates limit, market, stop and oco orders with exact bodies", async () => {
    const { client, mock } = setup();
    const orders = mock.endpoint("private_post_odr_orders");
    const created = await client.createOrder(
      "BTC/IRT",
      "limit",
      "buy",
      new Decimal("0.001"),
      3100000000,
      { clientOrderId: "mm-bid-1" },
    );
    expect(orders.last.body).toEqual({
      symbol: "BTC_IRT",
      type: "limit",
      side: "buy",
      base_amount: "0.001",
      price: "3100000000",
      identifier: "mm-bid-1",
    });
    expect([created.id, created.status]).toEqual(["535179385", "open"]);
    await client.createOrder("USDT/IRT", "market", "buy", null, 5, { quoteAmount: "1000000" });
    expect(orders.last.body).toEqual({
      symbol: "USDT_IRT",
      type: "market",
      side: "buy",
      quote_amount: "1000000",
    });
    await client.createOrder("BTC/USDT", "oco", "sell", 1, 57990, {
      triggerPrice: 58000,
      takeProfitPrice: 70000,
      extra: "x",
    });
    expect(orders.last.body).toEqual({
      symbol: "BTC_USDT",
      type: "oco",
      side: "sell",
      base_amount: "1",
      price: "57990",
      stop_price: "58000",
      oco_target_price: "70000",
      extra: "x",
    });
  });

  it.each([
    [["BTC/IRT", "limit", "buy", null, 1], /amount/],
    [["BTC/IRT", "limit", "buy", 1, null], /price/],
    [["BTC/IRT", "market", "buy", null, null], /amount or params/],
    [["BTC/IRT", "market", "buy", 1, null, { quoteAmount: 10 }], /only one/],
    [["BTC/IRT", "stop_limit", "buy", 1, 1], /stopPrice/],
    [["BTC/IRT", "oco", "buy", 1, 1, { stopPrice: 1 }], /takeProfitPrice/],
    [["BTC/IRT", "trailing", "buy", 1, 1], /type/],
    [["BTC/IRT", "limit", "long", 1, 1], /side/],
    [["BTC/IRT", "limit", "buy", 0, 1], /amount/],
    [["BTC/IRT", "limit", "buy", 1, -5], /price/],
    [["BTC/IRT", "stop_limit", "buy", 1, 1, { stopPrice: 0 }], /stopPrice/],
    [["BTC/IRT", "stop_limit", "buy", 1, 1, { stopPrice: 1, triggerPrice: 2 }], /both/],
    [["BTC/IRT", "market", "buy", null, null, { quoteAmount: 0 }], /quoteAmount/],
  ] as const)("validates %j before sending", async (args, message) => {
    const { client, mock } = setup();
    const orders = mock.endpoint("private_post_odr_orders");
    await expect((client.createOrder as any)(...args)).rejects.toThrow(message);
    expect(orders.count).toBe(0);
  });

  it("maps insufficient funds", async () => {
    const { client, mock } = setup();
    mock.endpoint("private_post_odr_orders", {
      status: 406,
      body: { detail: "insufficent_balance" },
    });
    await expect(client.createOrder("BTC/IRT", "limit", "buy", 1, 1)).rejects.toBeInstanceOf(
      errors.InsufficientFunds,
    );
  });

  it("bulk create and its limits", async () => {
    const { client, mock } = setup();
    const bulk = mock.endpoint("private_post_odr_orders_bulk");
    const result = await client.createOrders([
      {
        symbol: "BTC/IRT",
        type: "limit",
        side: "buy",
        amount: "0.001",
        price: "3100000000",
        params: { clientOrderId: "a" },
      },
      { symbol: "BTC/IRT", type: "limit", side: "buy", amount: "0.001", price: "3090000000" },
    ]);
    expect(bulk.last.body).toEqual([
      {
        symbol: "BTC_IRT",
        type: "limit",
        side: "buy",
        base_amount: "0.001",
        price: "3100000000",
        identifier: "a",
      },
      { symbol: "BTC_IRT", type: "limit", side: "buy", base_amount: "0.001", price: "3090000000" },
    ]);
    expect(result.map((o) => o.id)).toEqual(["535179385", "535179386"]);
    const one = { symbol: "BTC/IRT", type: "limit", side: "buy", amount: 1, price: 1 };
    await expect(client.createOrders(Array(11).fill(one))).rejects.toThrow(/at most 10/);
    await expect(client.createOrders([])).rejects.toThrow(/at least one/);
  });

  it("bulk create uses both bulk buckets", async () => {
    const { client, mock, time } = setup({ rateLimits: { order_bulk_cancel: "1/hour" } });
    mock.endpoint("private_post_odr_orders_bulk");
    mock.endpoint("private_delete_odr_orders_bulk");
    await client.createOrders([
      { symbol: "BTC/IRT", type: "limit", side: "buy", amount: 1, price: 1 },
    ]);
    await client.cancelOrders({ ids: [1] });
    expect(time.sleeps).toEqual([3600]);
  });

  it("reads orders", async () => {
    const { client, mock } = setup();
    const one = mock.endpoint("private_get_odr_orders_id");
    expect((await client.fetchOrder(535179385)).clientOrderId).toBe("mm-bid-1");
    expect(one.last.url.pathname).toBe("/api/v1/odr/orders/535179385/");
    mock.endpoint("private_get_odr_orders_id", { status: 404, body: { detail: "Not found." } });
    await expect(client.fetchOrder("1")).rejects.toBeInstanceOf(errors.OrderNotFound);
    const list = mock.endpoint("private_get_odr_orders");
    const result = await client.fetchOrders("BTC/IRT", 1793083530123, 2, { side: "buy" });
    const p = list.last.url.searchParams;
    expect([p.get("symbol"), p.get("limit"), p.get("side"), p.get("start")]).toEqual([
      "BTC_IRT",
      "2",
      "buy",
      "2026-10-27T06:45:30.123+00:00",
    ]);
    expect(result.map((o) => o.id)).toEqual(["535179300", "535179385"]);
    await client.fetchOpenOrders();
    expect(list.last.url.searchParams.get("state")).toBe("initial,active");
    await client.fetchClosedOrders();
    expect(list.last.url.searchParams.get("state")).toBe("closed");
  });

  it("paginates by id cursor and stops safely", async () => {
    const { client, mock } = setup();
    const page = (...ids: number[]) => ({ status: 200, body: ids.map((id) => ({ ...order, id })) });
    const list = mock.on("GET", "/api/v1/odr/orders/", [page(30, 20), page(10)]);
    expect(
      (await client.fetchOrders(undefined, undefined, 2, { paginate: true })).map((o) => o.id),
    ).toEqual(["10", "20", "30"]);
    expect(list.calls[0]!.url.searchParams.has("offset")).toBe(false);
    expect(list.calls[1]!.url.searchParams.get("offset")).toBe("20");
    const full = Array.from({ length: 250 }, (_, i) => 1000 + i);
    const open = mock.on("GET", "/api/v1/odr/orders/", [page(...full), page(5)]);
    expect(
      (await client.fetchOpenOrders(undefined, undefined, undefined, { paginate: true })).length,
    ).toBe(251);
    expect(open.calls[0]!.url.searchParams.get("limit")).toBe("250");
    const stuck = mock.on("GET", "/api/v1/odr/orders/", page(2, 1));
    expect((await client.fetchOrders(undefined, undefined, 2, { paginate: true })).length).toBe(2);
    expect(stuck.count).toBe(2);
    const pages = mock.on("GET", "/api/v1/odr/orders/", [
      page(92, 91),
      page(82, 81),
      page(72, 71),
      page(62, 61),
    ]);
    await client.fetchOrders(undefined, undefined, 2, { paginate: true, maxPages: 3 });
    expect(pages.count).toBe(3);
    const empty = mock.on("GET", "/api/v1/odr/orders/", page());
    expect(await client.fetchOrders(undefined, undefined, undefined, { paginate: true })).toEqual(
      [],
    );
    expect(empty.count).toBe(1);
  });

  it("cancels", async () => {
    const { client, mock } = setup();
    const cancel = mock.endpoint("private_delete_odr_orders_id");
    expect(await client.cancelOrder(7)).toEqual({ id: "7", clientOrderId: null, info: null });
    expect(cancel.last.url.pathname).toBe("/api/v1/odr/orders/7/");
    const byId = mock.endpoint("private_delete_odr_orders_identifier_identifier");
    expect(await client.cancelOrderByIdentifier("mm-bid-1")).toEqual({
      id: null,
      clientOrderId: "mm-bid-1",
      info: null,
    });
    expect(byId.last.url.pathname).toBe("/api/v1/odr/orders/identifier/mm-bid-1/");
    mock.endpoint("private_delete_odr_orders_id", {
      status: 406,
      body: { code: "cancel_order_not_allowed" },
    });
    await expect(client.cancelOrder(7)).rejects.toBeInstanceOf(errors.InvalidOrder);
    const bulk = mock.endpoint("private_delete_odr_orders_bulk");
    const result = await client.cancelOrders({ ids: [535179385, "535179386"] });
    expect(bulk.last.body).toEqual({ ids: ["535179385", "535179386"] });
    expect([result.canceled, result.notCanceled]).toEqual([["535179385"], ["535179386"]]);
    mock.endpoint("private_delete_odr_orders_bulk", { body: { canceled_orders: ["a"] } });
    expect((await client.cancelOrders({ identifiers: ["a"] })).notCanceled).toEqual([]);
    mock.endpoint("private_delete_odr_orders_bulk", { body: null });
    expect((await client.cancelOrders({ identifiers: ["a"] })).canceled).toEqual([]);
    await expect(client.cancelOrders({})).rejects.toThrow(/exactly one/);
    await expect(client.cancelOrders({ ids: [1], identifiers: ["a"] })).rejects.toThrow(
      /exactly one/,
    );
    await expect(
      client.cancelOrders({ ids: Array.from({ length: 11 }, (_, i) => i) }),
    ).rejects.toThrow(/at most 10/);
  });

  it("fills within 24 hours", async () => {
    const { client, mock } = setup();
    const fills = mock.endpoint("private_get_odr_fills");
    const since = NOW * 1000 - 3_600_000;
    const trades = await client.fetchMyTrades("BTC/IRT", since, 100);
    expect([
      fills.last.url.searchParams.get("start"),
      fills.last.url.searchParams.get("limit"),
    ]).toEqual([String(since / 1000), "100"]);
    expect(trades[0]!.fee!.currency).toBe("IRT");
    await client.fetchMyTrades();
    await expect(client.fetchMyTrades(undefined, NOW * 1000 - 86_401_000)).rejects.toThrow(
      /24 hours/,
    );
  });

  it("order history follows the cursor, resends filters, dedupes and stops on repeats", async () => {
    const { client, mock } = setup();
    const row = body("private_get_odr_order_history").results[0];
    const history = mock.on("GET", "/api/v1/odr/order_history/", [
      { status: 200, body: { results: [row], next_cursor: "c1", has_next: true } },
      { status: 200, body: { results: [{ ...row, id: 2 }], next_cursor: "", has_next: false } },
    ]);
    const result = await client.fetchOrderHistory("BTC/IRT", 1, 2, 1, {
      side: "buy",
      type: "market",
      paginate: true,
    });
    expect(Object.fromEntries(history.calls[0]!.url.searchParams)).toEqual({
      symbol: "BTC_IRT",
      start: "1",
      end: "2",
      limit: "1",
      side: "buy",
      type: "market",
    });
    expect(Object.fromEntries(history.calls[1]!.url.searchParams)).toEqual({
      symbol: "BTC_IRT",
      limit: "1",
      side: "buy",
      type: "market",
      cursor: "c1",
    });
    expect(result.map((o) => o.id)).toEqual(["535100000", "2"]);
    const same = mock.on("GET", "/api/v1/odr/order_history/", {
      status: 200,
      body: { results: [row], next_cursor: "same", has_next: true },
    });
    expect(
      (
        await client.fetchOrderHistory(undefined, undefined, undefined, undefined, {
          paginate: true,
        })
      ).length,
    ).toBe(1);
    expect(same.count).toBe(2);
    mock.on("GET", "/api/v1/odr/order_history/", { status: 200, body: {} });
    expect(await client.fetchOrderHistory()).toEqual([]);
  });

  it.each([
    [[undefined, undefined, undefined, 201], /200/],
    [[undefined, undefined, undefined, 0], /200/],
    [[undefined, 0, 91 * 86_400_000], /90 days/],
    [[undefined, 5, 5], /before/],
  ] as const)("order history validates %j", async (args, message) => {
    const { client } = setup();
    await expect((client.fetchOrderHistory as any)(...args)).rejects.toThrow(message);
  });
});
