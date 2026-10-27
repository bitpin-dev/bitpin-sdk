// Live, read-only checks against the real Bitpin API. Never run in CI.
//   BITPIN_LIVE=1 [BITPIN_API_KEY=... BITPIN_SECRET_KEY=...] npm run test:live
// Every response is parsed by the SDK and compared with the shape of its fixture, so a server
// change (renamed field, new type) shows up here before users hit it.
import { describe, expect, it } from "vitest";
import { Bitpin } from "../../src/index.js";
import { fixture } from "../helpers.js";

const LIVE = process.env.BITPIN_LIVE === "1";
const PRIVATE = LIVE && Boolean(process.env.BITPIN_API_KEY && process.env.BITPIN_SECRET_KEY);
const ALLOWED_WRITES = [
  "/api/v1/usr/authenticate/",
  "/api/v1/usr/refresh_token/",
  "/api/v1/usr/ws-info/",
];

/** fetch that refuses anything but reads and the auth calls. */
const readOnlyFetch: typeof fetch = async (input, init) => {
  const method = init?.method ?? "GET";
  const path = new URL(String(input)).pathname;
  if (method !== "GET" && !ALLOWED_WRITES.includes(path))
    throw new Error(`live tests are read-only: refused ${method} ${path}`);
  return fetch(input, init);
};

function typeOf(value: unknown): string {
  return value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
}

/** Every key of the fixture's first row exists live with the same type (null matches anything). */
function expectShape(endpointId: string, live: unknown): void {
  const sample = fixture(endpointId).body;
  const first = (v: any) => (Array.isArray(v) ? v[0] : v?.results ? v.results[0] : v);
  const want = first(sample);
  const got = first(live);
  if (!want || !got || typeof want !== "object") return;
  for (const [key, value] of Object.entries(want)) {
    expect(got, `${endpointId}: missing field ${key}`).toHaveProperty(key);
    const actual = (got as any)[key];
    if (value !== null && actual !== null)
      expect(typeOf(actual), `${endpointId}.${key}`).toBe(typeOf(value));
  }
}

const client = new Bitpin({ fetch: readOnlyFetch, maxRetries: 1 });

describe.runIf(LIVE)("live public API", () => {
  const symbol = "USDT/IRT";
  it.each([
    ["public_get_mkt_currencies", () => client.publicGetMktCurrencies()],
    ["public_get_mkt_markets", () => client.publicGetMktMarkets()],
    ["public_get_mkt_networks", () => client.publicGetMktNetworks()],
    ["public_get_mkt_tickers", () => client.publicGetMktTickers()],
    [
      "public_get_mth_orderbook_symbol",
      () => client.publicGetMthOrderbookSymbol({ symbol: "USDT_IRT" }),
    ],
    [
      "public_get_mth_matches_symbol",
      () => client.publicGetMthMatchesSymbol({ symbol: "USDT_IRT" }),
    ],
  ] as const)("%s keeps its shape", async (endpointId, call) => {
    expectShape(endpointId, await call());
  });

  it("unified methods parse live data", async () => {
    expect(Object.keys(await client.loadMarkets()).length).toBeGreaterThan(0);
    expect((await client.fetchTicker(symbol)).last).not.toBeNull();
    expect((await client.fetchOrderBook(symbol)).bids.length).toBeGreaterThan(0);
    expect((await client.fetchOHLCV(symbol, "1h", undefined, 5)).length).toBeGreaterThan(0);
    expect(Array.isArray(await client.fetchTrades(symbol))).toBe(true);
  });
});

describe.runIf(PRIVATE)("live private reads", () => {
  it.each([
    ["private_get_mkt_commissions", () => client.privateGetMktCommissions()],
    ["private_get_odr_orders", () => client.privateGetOdrOrders({ limit: 5 })],
    ["private_get_odr_fills", () => client.privateGetOdrFills({ limit: 5 })],
    ["private_get_odr_order_history", () => client.privateGetOdrOrderHistory({ limit: 5 })],
    ["private_get_wlt_wallets", () => client.privateGetWltWallets({ limit: 5 })],
    ["private_get_wlt_account_numbers", () => client.privateGetWltAccountNumbers()],
    ["private_get_wlt_networks", () => client.privateGetWltNetworks({ currency_code: "USDT" })],
    ["private_get_wlt_deposits", () => client.privateGetWltDeposits({ limit: 5 })],
    ["private_get_wlt_withdraws", () => client.privateGetWltWithdraws({ limit: 5 })],
  ] as const)("%s keeps its shape", async (endpointId, call) => {
    expectShape(endpointId, await call());
  });

  it("unified private reads parse live data", async () => {
    expect(typeof (await client.fetchBalance())).toBe("object");
    expect(Array.isArray(await client.fetchOpenOrders())).toBe(true);
    expect(Array.isArray(await client.fetchMyTrades())).toBe(true);
  });
});

describe.runIf(!LIVE)("live tests", () => {
  it.skip("set BITPIN_LIVE=1 to run them", () => undefined);
});
