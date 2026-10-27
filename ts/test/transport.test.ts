import { describe, expect, it } from "vitest";
import { ENDPOINTS } from "../src/generated/spec.js";
import { Bitpin, errors, MemoryTokenStore, VERSION } from "../src/index.js";
import { body, FakeTime, MockFetch, makeClient, makeJwt, NOW, setup } from "./helpers.js";

describe("transport", () => {
  it("has an implicit method per endpoint", () => {
    const { client } = setup();
    for (const e of Object.values(ENDPOINTS))
      expect(typeof (client as any)[e.implicit]).toBe("function");
  });

  it("public calls send no token and identify the SDK", async () => {
    const { client, mock } = setup();
    const tickers = mock.endpoint("public_get_mkt_tickers");
    await client.publicGetMktTickers();
    expect(tickers.last.headers.get("authorization")).toBeNull();
    expect(tickers.last.headers.get("user-agent")).toBe(`bitpin-sdk-ts/${VERSION}`);
    expect(tickers.last.headers.get("accept")).toBe("application/json");
  });

  it("authenticates once and sends the bearer token", async () => {
    const { client, mock, auth } = setup();
    const wallets = mock.endpoint("private_get_wlt_wallets");
    await client.privateGetWltWallets();
    await client.privateGetWltWallets();
    expect(auth.count).toBe(1);
    expect(auth.last.body).toEqual({ api_key: "test-key", secret_key: "test-secret" });
    expect(wallets.last.headers.get("authorization")).toBe(
      `Bearer ${body("credentials_post_usr_authenticate").access}`,
    );
  });

  it("implicit methods split path params from the query", async () => {
    const { client, mock } = setup();
    const book = mock.endpoint("public_get_mth_orderbook_symbol");
    await client.publicGetMthOrderbookSymbol({ symbol: "BTC_IRT", limit: 20 });
    expect(book.last.url.pathname).toBe("/api/v1/mth/orderbook/BTC_IRT/");
    expect(book.last.url.searchParams.get("limit")).toBe("20");
    const create = mock.endpoint("private_post_odr_orders");
    await client.privatePostOdrOrders({ symbol: "BTC_IRT" });
    expect(create.last.body).toEqual({ symbol: "BTC_IRT" });
    const bulk = mock.endpoint("private_post_odr_orders_bulk");
    await client.privatePostOdrOrdersBulk({}, [{ symbol: "BTC_IRT" }]);
    expect(bulk.last.body).toEqual([{ symbol: "BTC_IRT" }]);
  });

  it("private calls need credentials", async () => {
    const mock = new MockFetch();
    const client = makeClient(mock, new FakeTime(), { apiKey: undefined, secretKey: undefined });
    await expect(client.privateGetWltWallets()).rejects.toThrow(/apiKey and secretKey/);
  });

  it("refreshes before expiry and falls back to authenticate", async () => {
    const { client, mock, time } = setup();
    const auth = mock.endpoint("credentials_post_usr_authenticate", {
      body: { access: makeJwt(NOW + 900), refresh: makeJwt(NOW + 86400) },
    });
    const refresh = mock.endpoint("credentials_post_usr_refresh_token", {
      body: { access: makeJwt(NOW + 1800) },
    });
    const wallets = mock.endpoint("private_get_wlt_wallets");
    await client.privateGetWltWallets();
    time.now += 840;
    await client.privateGetWltWallets();
    expect(refresh.count).toBe(1);
    expect(refresh.last.body).toEqual({ refresh: makeJwt(NOW + 86400) });
    expect(wallets.last.headers.get("authorization")).toBe(`Bearer ${makeJwt(NOW + 1800)}`);
    mock.endpoint("credentials_post_usr_refresh_token", {
      status: 401,
      body: { detail: "expired" },
    });
    time.now += 1800;
    await client.privateGetWltWallets();
    expect(auth.count).toBe(2);
  });

  it("a refresh failing for another reason propagates", async () => {
    const { client, mock, time } = setup();
    mock.endpoint("credentials_post_usr_authenticate", {
      body: { access: makeJwt(NOW + 900), refresh: makeJwt(NOW + 86400) },
    });
    mock.endpoint("private_get_wlt_wallets");
    await client.privateGetWltWallets();
    mock.endpoint("credentials_post_usr_refresh_token", { status: 503, body: null });
    time.now += 840;
    await expect(client.privateGetWltWallets()).rejects.toBeInstanceOf(errors.ExchangeNotAvailable);
  });

  it("a 401 refreshes once and retries once; a second 401 throws", async () => {
    const { client, mock, auth } = setup();
    mock.endpoint("credentials_post_usr_refresh_token");
    const wallets = mock.on("GET", "/api/v1/wlt/wallets/", [
      { status: 401, body: { detail: "revoked" } },
      { status: 200, body: [] },
    ]);
    expect(await client.privateGetWltWallets()).toEqual([]);
    expect(wallets.count).toBe(2);
    expect(auth.count).toBe(1);
    mock.endpoint("private_get_wlt_wallets", { status: 401, body: { detail: "revoked" } });
    await expect(client.privateGetWltWallets()).rejects.toBeInstanceOf(errors.AuthenticationError);
  });

  it("concurrent calls authenticate once", async () => {
    const { client, mock, auth } = setup();
    mock.endpoint("private_get_wlt_wallets");
    await Promise.all(Array.from({ length: 10 }, () => client.privateGetWltWallets()));
    expect(auth.count).toBe(1);
  });

  it("tokens come from and go to the store", async () => {
    const store = new MemoryTokenStore();
    const mock = new MockFetch();
    const time = new FakeTime();
    const auth = mock.endpoint("credentials_post_usr_authenticate");
    mock.endpoint("private_get_wlt_wallets");
    await makeClient(mock, time, { tokenStore: store }).privateGetWltWallets();
    await makeClient(mock, time, { tokenStore: store }).privateGetWltWallets();
    expect(auth.count).toBe(1);
  });

  it("retries idempotent GETs with backoff, up to maxRetries", async () => {
    const { client, mock, time } = setup();
    const tickers = mock.on("GET", "/api/v1/mkt/tickers/", [
      new TypeError("fetch failed"),
      { status: 200, body: [] },
    ]);
    expect(await client.publicGetMktTickers()).toEqual([]);
    expect(tickers.count).toBe(2);
    expect(time.sleeps).toEqual([0.5]);
    const few = setup({ maxRetries: 2 });
    const down = few.mock.endpoint("public_get_mkt_tickers", { status: 503, body: null });
    await expect(few.client.publicGetMktTickers()).rejects.toBeInstanceOf(
      errors.ExchangeNotAvailable,
    );
    expect(down.count).toBe(3);
    expect(few.time.sleeps).toEqual([0.5, 1]);
  });

  it.each([
    { status: 429, body: { detail: "Expected available in 1 seconds." } },
    Object.assign(new Error("slow"), { name: "TimeoutError" }),
    { status: 503 },
  ])("never retries create order (%#)", async (failure) => {
    const { client, mock } = setup();
    const orders = mock.on("POST", "/api/v1/odr/orders/", [
      failure as never,
      { status: 201, body: {} },
    ]);
    await expect(client.privatePostOdrOrders({ symbol: "BTC_IRT" })).rejects.toBeInstanceOf(
      errors.NetworkError,
    );
    expect(orders.count).toBe(1);
  });

  it("maps timeouts and transport errors", async () => {
    const { client, mock } = setup({ maxRetries: 0 });
    mock.on("GET", "/api/v1/mkt/tickers/", Object.assign(new Error("x"), { name: "AbortError" }));
    await expect(client.publicGetMktTickers()).rejects.toBeInstanceOf(errors.RequestTimeout);
    mock.on("GET", "/api/v1/mkt/tickers/", new TypeError("fetch failed"));
    const error = await client.publicGetMktTickers().catch((e) => e);
    expect(error.constructor).toBe(errors.NetworkError);
    expect(error.cause).toBeInstanceOf(TypeError);
    mock.on("GET", "/api/v1/mkt/tickers/", () => {
      throw "weird"; // a rejection that isn't an Error
    });
    await expect(client.publicGetMktTickers()).rejects.toThrow(/network error/);
  });

  it("waits out a short 429 on GETs, throws a long one", async () => {
    const { client, mock, time } = setup();
    mock.on("GET", "/api/v1/mkt/tickers/", [
      { status: 429, body: { detail: "Expected available in 2 seconds." } },
      { status: 200, body: [] },
    ]);
    await client.publicGetMktTickers();
    expect(time.sleeps).toEqual([2]);
    mock.endpoint("public_get_mkt_tickers", {
      status: 429,
      body: { detail: "Expected available in 86398 seconds." },
    });
    const error = await client.publicGetMktTickers().catch((e) => e);
    expect(error.retryAfter).toBe(86398);
  });

  it("client-side limiter waits and can be disabled", async () => {
    const limited = setup({ rateLimits: { tickers: "2/min" } });
    limited.mock.endpoint("public_get_mkt_tickers");
    for (let i = 0; i < 3; i++) await limited.client.publicGetMktTickers();
    expect(limited.time.sleeps).toEqual([60]);
    const free = setup({ rateLimits: { tickers: "1/min" }, enableRateLimit: false });
    free.mock.endpoint("public_get_mkt_tickers");
    for (let i = 0; i < 3; i++) await free.client.publicGetMktTickers();
    expect(free.time.sleeps).toEqual([]);
  });

  it("spreads a concurrent burst instead of firing it together", async () => {
    const mock = new MockFetch();
    const time = new FakeTime();
    const sleeps: number[] = [];
    mock.endpoint("public_get_mth_orderbook_symbol");
    const client = makeClient(mock, time, {
      rateLimits: { orderbook: "2/sec" },
      sleep: async (s) => {
        sleeps.push(s);
      },
    });
    await Promise.all(Array.from({ length: 8 }, () => client.fetchOrderBook("BTC/IRT")));
    expect(sleeps.sort()).toEqual([1, 1, 2, 2, 3, 3]);
  });

  it("204, bad JSON, and text error bodies", async () => {
    const { client, mock } = setup({ maxRetries: 0 });
    mock.endpoint("private_delete_odr_orders_id");
    expect(await client.privateDeleteOdrOrdersId({ id: 1 })).toBeNull();
    mock.on("GET", "/api/v1/mkt/tickers/", { status: 502, text: "<html>bad gateway</html>" });
    const error = await client.publicGetMktTickers().catch((e) => e);
    expect(error).toBeInstanceOf(errors.ExchangeNotAvailable);
    expect(error.body).toBe("<html>bad gateway</html>");
    mock.on("GET", "/api/v1/mkt/tickers/", { status: 200, text: "not json" });
    await expect(client.publicGetMktTickers()).rejects.toThrow(/invalid JSON/);
  });

  it("keeps secrets out of errors, causes and printing", async () => {
    const { client, mock } = setup({ maxRetries: 0 });
    mock.endpoint("credentials_post_usr_authenticate", {
      status: 406,
      body: { detail: "api_credential_wrong" },
    });
    const error = await client.privateGetWltWallets().catch((e) => e);
    expect(error).toBeInstanceOf(errors.AuthenticationError);
    const text = `${error.message} ${JSON.stringify(error.body)} ${String(client)} ${JSON.stringify(client)}`;
    expect(text).not.toContain("test-secret");
    expect(text).not.toContain("test-key");
    mock.on("POST", "/api/v1/usr/authenticate/", new TypeError("fetch failed"));
    const network = await client.privateGetWltWallets().catch((e) => e);
    expect(network).toBeInstanceOf(errors.NetworkError);
    expect(network.cause).toBeUndefined();
  });

  it("a late 401 for a replaced token doesn't refresh again", async () => {
    const { client, mock } = setup();
    const first = body("credentials_post_usr_authenticate").access;
    const refresh = mock.endpoint("credentials_post_usr_refresh_token", {
      body: { access: makeJwt(NOW + 5000) },
    });
    mock.endpoint("private_get_wlt_wallets");
    await client.privateGetWltWallets();
    (client as any).tokens.setAccess({ access: makeJwt(NOW + 4000) });
    (client as any).tokens.expireAccess(first);
    await client.privateGetWltWallets();
    expect(refresh.count).toBe(0);
  });

  it("derives the key id once per client", async () => {
    const { client, mock } = setup();
    mock.endpoint("private_get_wlt_wallets");
    await client.privateGetWltWallets();
    const id = (client as any).storeKey;
    await client.privateGetWltWallets();
    expect((client as any).storeKey).toBe(id);
  });

  it("uses the global fetch, real clock and sleep by default", async () => {
    const original = globalThis.fetch;
    const mock = new MockFetch();
    mock.endpoint("public_get_mkt_tickers");
    globalThis.fetch = mock.fetch as typeof fetch;
    try {
      const client = new Bitpin({ rateLimits: { tickers: "1/sec" } });
      await client.publicGetMktTickers();
      const started = Date.now();
      await client.publicGetMktTickers();
      expect(Date.now() - started).toBeGreaterThanOrEqual(900);
      expect(client.id).toBe("bitpin");
    } finally {
      globalThis.fetch = original;
    }
  });

  it("reads the environment", () => {
    process.env.BITPIN_API_KEY = "env-key";
    process.env.BITPIN_SECRET_KEY = "env-secret";
    try {
      expect(new Bitpin().config.hasCredentials).toBe(true);
    } finally {
      delete process.env.BITPIN_API_KEY;
      delete process.env.BITPIN_SECRET_KEY;
    }
  });
});
