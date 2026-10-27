import { afterEach, describe, expect, it, vi } from "vitest";
import { main as marketMaker, quotes } from "../../examples/ts/market-maker.ts";
import { main as placeAndCancel } from "../../examples/ts/place-and-cancel.ts";
import { main as quickstart } from "../../examples/ts/quickstart.ts";
import { Decimal, NetworkError } from "../src/index.js";
import { FakeTime, MockFetch } from "./helpers.js";

const writes = (mock: MockFetch) =>
  mock.calls
    .filter((c) => c.method !== "GET" && !c.url.pathname.includes("/usr/"))
    .map((c) => `${c.method} ${c.url.pathname}`);

function env() {
  const mock = new MockFetch();
  const time = new FakeTime();
  for (const id of [
    "public_get_mkt_markets",
    "public_get_mkt_tickers",
    "private_get_wlt_wallets",
    "credentials_post_usr_authenticate",
    "public_get_mth_orderbook_symbol",
    "private_post_odr_orders_bulk",
    "private_delete_odr_orders_bulk",
    "private_post_odr_orders",
    "private_get_odr_orders_id",
    "private_delete_odr_orders_identifier_identifier",
  ]) {
    mock.endpoint(id);
  }
  return {
    mock,
    options: {
      apiKey: "k",
      secretKey: "s",
      fetch: mock.fetch,
      clock: time.clock,
      sleep: time.sleep,
    },
  };
}

describe("examples", () => {
  const log = vi.spyOn(console, "log").mockImplementation(() => undefined);
  afterEach(() => log.mockClear());
  const output = () => log.mock.calls.map((c) => c.join(" ")).join("\n");

  it("quickstart reads only", async () => {
    const { mock, options } = env();
    expect(await quickstart(["--symbol", "BTC/IRT"], options)).toBe(0);
    expect(output()).toContain("3 markets");
    expect(output()).toContain("non-zero balances");
    expect(writes(mock)).toEqual([]);
    const anon = env();
    await quickstart([], { fetch: anon.mock.fetch });
    expect(output()).toContain("Set BITPIN_API_KEY");
  });

  it("place-and-cancel is dry-run by default and live with --live", async () => {
    const { mock, options } = env();
    expect(await placeAndCancel(["--price", "90000", "--amount", "10"], options)).toBe(0);
    expect(output()).toContain("DRY-RUN createOrder");
    expect(mock.calls.length).toBe(0);
    await placeAndCancel(["--price", "90000", "--amount", "10", "--live"], options);
    expect(writes(mock)[0]).toBe("POST /api/v1/odr/orders/");
    expect(writes(mock)[1]).toMatch(/^DELETE \/api\/v1\/odr\/orders\/identifier\/example-/);
    await expect(placeAndCancel([], options)).rejects.toThrow(/required/);
  });

  it("market maker: dry-run, live replace, and cancel on error", async () => {
    const dry = env();
    expect(
      await marketMaker(
        ["--symbol", "BTC/IRT", "--size", "0.001", "--iterations", "2"],
        dry.options,
        async () => undefined,
      ),
    ).toBe(0);
    expect(output().match(/DRY-RUN createOrders/g)?.length).toBe(2);
    expect(writes(dry.mock)).toEqual([]);

    const live = env();
    await marketMaker(
      ["--symbol", "BTC/IRT", "--size", "0.001", "--iterations", "2", "--live"],
      live.options,
      async () => undefined,
    );
    expect(writes(live.mock)).toEqual([
      "POST /api/v1/odr/orders/bulk/",
      "DELETE /api/v1/odr/orders/bulk/",
      "POST /api/v1/odr/orders/bulk/",
      "DELETE /api/v1/odr/orders/bulk/",
    ]);

    const failing = env();
    failing.mock.on("GET", "/api/v1/mth/orderbook/*", [
      { status: 200, body: { asks: [["2", "1"]], bids: [["1", "1"]] } },
      new TypeError("down"),
    ]);
    await expect(
      marketMaker(
        ["--symbol", "BTC/IRT", "--size", "1", "--iterations", "2", "--live"],
        { ...failing.options, maxRetries: 0 },
        async () => undefined,
      ),
    ).rejects.toBeInstanceOf(NetworkError);
    expect(writes(failing.mock).at(-1)).toBe("DELETE /api/v1/odr/orders/bulk/");

    const empty = env();
    empty.mock.on("GET", "/api/v1/mth/orderbook/*", { status: 200, body: { asks: [], bids: [] } });
    await marketMaker(
      ["--symbol", "BTC/IRT", "--size", "1", "--iterations", "1"],
      empty.options,
      async () => undefined,
    );
    expect(output()).toContain("empty book");
    await expect(marketMaker([], empty.options)).rejects.toThrow(/--size/);

    const poor = env();
    poor.mock.endpoint("private_post_odr_orders_bulk", {
      status: 406,
      body: { detail: "insufficent_balance" },
    });
    await marketMaker(
      ["--symbol", "BTC/IRT", "--size", "1", "--iterations", "1", "--live"],
      poor.options,
      async () => undefined,
    );
    expect(output()).toContain("insufficient funds");
  });

  it("quotes round away from the mid", () => {
    expect(quotes(new Decimal("100.5"), new Decimal(20), new Decimal(1)).map(String)).toEqual([
      "100",
      "101",
    ]);
  });
});
