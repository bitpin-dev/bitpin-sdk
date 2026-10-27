import { describe, expect, it } from "vitest";
import { RateLimit, resolveConfig } from "../src/config.js";
import { jwtExp, TokenState } from "../src/core/auth.js";
import { mapError, notSupported } from "../src/core/errors.js";
import { Decimal, fmtDecimal, toDecimal } from "../src/core/numbers.js";
import { SlidingWindowLimiter } from "../src/core/ratelimit.js";
import { buildRequest } from "../src/core/request.js";
import { toMarketId, toSymbol } from "../src/core/symbols.js";
import * as errors from "../src/errors.js";
import { makeJwt } from "./helpers.js";

describe("numbers", () => {
  it.each([
    [new Decimal("1E-8"), "0.00000001"],
    [0.1, "0.1"],
    [1e-7, "0.0000001"],
    [100, "100"],
    [new Decimal("1E+3"), "1000"],
    ["63.0", "63"],
    ["0.000", "0"],
    [new Decimal("-1.50"), "-1.5"],
    ["-0", "0"],
    [3145737420, "3145737420"],
  ])("fmtDecimal(%s) = %s", (value, expected) => {
    expect(fmtDecimal(value)).toBe(expected);
  });

  it("parses and rejects", () => {
    expect(toDecimal(0.1)?.toString()).toBe("0.1");
    expect(toDecimal(null)).toBeNull();
    expect(toDecimal(undefined)).toBeNull();
    expect(toDecimal("")).toBeNull();
    expect(() => toDecimal("abc")).toThrow(/not a number/);
    expect(() => toDecimal(true as never)).toThrow(/not a number/);
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, "NaN", "Infinity"]) {
      expect(() => fmtDecimal(bad)).toThrow(/not a finite number/);
    }
  });

  it("round-trips many values exactly", () => {
    for (let i = 0; i < 500; i++) {
      const d = new Decimal(Math.floor(Math.random() * 1e12)).div(new Decimal(10).pow(i % 13));
      expect(toDecimal(fmtDecimal(d))!.eq(d)).toBe(true);
      expect(fmtDecimal(d)).not.toMatch(/e/i);
    }
  });
});

describe("symbols", () => {
  it.each(["BTC/IRT", "btc/irt", "BTC_IRT", "btc_irt", " BTC/IRT "])("normalizes %s", (s) => {
    expect(toMarketId(s)).toBe("BTC_IRT");
  });
  it("keeps digits", () => expect(toMarketId("1INCH/USDT")).toBe("1INCH_USDT"));
  it.each(["BTCIRT", "BTC-IRT", "BTC/", "/IRT", "BTC/IRT/X", "", "BTC_I RT"])("rejects %j", (s) => {
    expect(() => toMarketId(s)).toThrow(errors.BadSymbol);
  });
  it("converts ids back", () => {
    expect(toSymbol("BTC_IRT")).toBe("BTC/IRT");
    expect(() => toSymbol("BTCIRT")).toThrow(errors.BadSymbol);
  });
});

describe("rate limiter", () => {
  it("waits for the oldest call to leave the window", () => {
    let now = 1000;
    const limiter = new SlidingWindowLimiter({ auth: new RateLimit(3, "min") }, () => now);
    for (const step of [0, 10, 20]) {
      now = 1000 + step;
      expect(limiter.reserve(["auth"])).toBe(0);
    }
    now = 1030;
    expect(limiter.delay(["auth"])).toBe(30);
    now = 1060;
    expect(limiter.delay(["auth"])).toBe(0);
  });

  it("spreads a burst over windows", () => {
    const limiter = new SlidingWindowLimiter({ a: new RateLimit(2, "sec") }, () => 1000);
    expect(Array.from({ length: 8 }, () => limiter.reserve(["a"]))).toEqual([
      0, 0, 1, 1, 2, 2, 3, 3,
    ]);
  });

  it("uses the longest delay across buckets and ignores unknown ones", () => {
    const limiter = new SlidingWindowLimiter(
      { a: new RateLimit(1, "sec"), b: new RateLimit(1, "min") },
      () => 1000,
    );
    expect(limiter.reserve(["a", "b", "x"])).toBe(0);
    expect(limiter.delay(["a", "b"])).toBe(60);
    expect(limiter.delay(["a"])).toBe(1);
    expect(limiter.delay(["x"])).toBe(0);
  });

  it("prunes old entries", () => {
    let now = 1000;
    const limiter = new SlidingWindowLimiter({ a: new RateLimit(2, "sec") }, () => now);
    limiter.reserve(["a"]);
    limiter.reserve(["a"]);
    now += 5;
    expect(limiter.reserve(["a"])).toBe(0);
    expect(limiter.size("a")).toBe(1);
  });
});

describe("config", () => {
  it("defaults come from the spec", () => {
    const config = resolveConfig({});
    expect(config.restUrl).toBe("https://api.bitpin.org");
    expect(config.wsUrl).toBe("wss://centrifugo.bitpin.org/connection/websocket");
    expect(config.rateLimit("auth")).toEqual(new RateLimit(3, "min"));
    expect(config.rateLimit("order_history")).toEqual(new RateLimit(5, "sec"));
    expect(config.timeout).toBe(10_000);
    expect(config.maxRetries).toBe(3);
    expect(config.enableRateLimit).toBe(true);
    expect(config.hasCredentials).toBe(false);
  });

  it("accepts overrides and ccxt keys", () => {
    const config = resolveConfig({
      apiKey: "k",
      secret: "s",
      rateLimits: { orderbook: "10800/min" },
    });
    expect(config.secretKey).toBe("s");
    expect(config.hasCredentials).toBe(true);
    expect(config.rateLimit("orderbook")).toEqual(new RateLimit(10_800, "min"));
    expect(config.rateLimit("matches")).toEqual(new RateLimit(60, "min"));
    expect(config.allRateLimits().auth).toEqual(new RateLimit(3, "min"));
  });

  it.each(["10/minute", "x/min", "0/min", "10"])("rejects rate limit %s", (bad) => {
    expect(() => RateLimit.parse(bad)).toThrow(/rate limit/);
  });

  it("rejects unknown buckets and bad values", () => {
    expect(() => resolveConfig({ rateLimits: { orderbok: "1/min" } })).toThrow(
      /unknown rate-limit bucket 'orderbok'/,
    );
    expect(() => resolveConfig({ maxRetries: -1 })).toThrow(/maxRetries/);
    expect(() => new RateLimit(0, "min")).toThrow(/rate limit/);
  });

  it("periods in seconds", () => {
    expect(
      [
        new RateLimit(1, "sec"),
        new RateLimit(1, "min"),
        new RateLimit(1, "hour"),
        new RateLimit(1, "day"),
      ].map((r) => r.periodSeconds),
    ).toEqual([1, 60, 3600, 86400]);
  });

  it("reads the environment", () => {
    const config = resolveConfig({}, { BITPIN_API_KEY: "ek", BITPIN_SECRET_KEY: "es" });
    expect(config.apiKey).toBe("ek");
    expect(config.secretKey).toBe("es");
  });

  it("hides secrets when printed", () => {
    const config = resolveConfig({ apiKey: "AKEY-123", secretKey: "SECRET-456" });
    const text = `${JSON.stringify(config)} ${String(config)}`;
    expect(text).not.toContain("AKEY-123");
    expect(text).not.toContain("SECRET-456");
    expect(text).toContain("***");
  });
});

describe("tokens", () => {
  const now = 1_000_000;

  it("reads exp and rejects junk", () => {
    expect(jwtExp(makeJwt(1234))).toBe(1234);
    expect(jwtExp("not-a-jwt")).toBeNull();
    expect(jwtExp("a.!!!.c")).toBeNull();
    const b64 = (s: string) => Buffer.from(s).toString("base64url");
    for (const raw of ['{"no":1}', '{"exp":"soon"}', '{"exp":true}', "[1]", "1e999"]) {
      expect(jwtExp(`e30.${b64(raw)}.sig`)).toBeNull();
    }
  });

  it("decides between ok, refresh and authenticate", () => {
    let t = now;
    const state = new TokenState(() => t);
    expect(state.action()).toBe("authenticate");
    state.setTokens({ access: makeJwt(now + 900), refresh: makeJwt(now + 86400) });
    expect(state.action()).toBe("ok");
    t += 900 - 121;
    expect(state.action()).toBe("ok");
    t += 1;
    expect(state.action()).toBe("refresh");
    t = now + 86400;
    expect(state.action()).toBe("authenticate");
  });

  it("keeps the refresh token on set_access and expires only the current token", () => {
    const state = new TokenState(() => now);
    const refresh = makeJwt(now + 86400);
    state.setTokens({ access: makeJwt(now + 900), refresh });
    const old = state.accessToken;
    state.setAccess({ access: makeJwt(now + 1800) });
    expect(state.tokens!.refresh).toBe(refresh);
    state.expireAccess(old!);
    expect(state.action()).toBe("ok");
    state.expireAccess(state.accessToken!);
    expect(state.action()).toBe("refresh");
    state.expireAccess();
    expect(state.action()).toBe("refresh");
    state.clear();
    expect(state.action()).toBe("authenticate");
    expect(state.accessToken).toBeNull();
    expect(() => state.setAccess({ access: "x" })).toThrow(/before setTokens/);
    new TokenState(() => now).expireAccess();
  });

  it("falls back to the spec lifetimes without exp", () => {
    const state = new TokenState(() => now);
    expect(state.setTokens({ access: "opaque", refresh: "opaque2" })).toEqual({
      access: "opaque",
      refresh: "opaque2",
      accessExp: now + 900,
      refreshExp: now + 2592000,
    });
    state.load({ access: "a", refresh: "r", accessExp: now + 900, refreshExp: now + 9000 });
    expect(state.action()).toBe("ok");
  });
});

describe("error mapping", () => {
  it.each([
    [
      "private_get_wlt_wallets",
      401,
      { detail: "bad", code: "token_not_valid" },
      errors.AuthenticationError,
    ],
    [
      "credentials_post_usr_authenticate",
      406,
      { detail: "api_credential_wrong" },
      errors.AuthenticationError,
    ],
    ["credentials_post_usr_ws_info", 406, { detail: "wrong ip" }, errors.AuthenticationError],
    ["private_post_wlt_address", 403, { detail: "kyc" }, errors.PermissionDenied],
    ["private_get_odr_orders_id", 404, { detail: "Not found." }, errors.OrderNotFound],
    ["private_delete_odr_orders_identifier_identifier", 404, {}, errors.OrderNotFound],
    ["public_get_mth_orderbook_symbol", 404, {}, errors.BadRequest],
    ["private_post_odr_orders", 406, { detail: "insufficent_balance" }, errors.InsufficientFunds],
    [
      "private_post_wlt_withdraws",
      406,
      { detail: "insufficent_pool_balance" },
      errors.InsufficientFunds,
    ],
    [
      "private_delete_odr_orders_id",
      406,
      { code: "cancel_order_not_allowed" },
      errors.InvalidOrder,
    ],
    ["private_delete_odr_orders_id", 406, { detail: "not allowed" }, errors.InvalidOrder],
    ["private_post_wlt_withdraws_verify_otp_id", 400, { code: "invalid_otp" }, errors.InvalidOTP],
    ["private_post_odr_orders", 400, { price: ["required"] }, errors.InvalidOrder],
    ["public_get_mkt_candles", 400, { detail: "too many" }, errors.BadRequest],
    [
      "private_get_wlt_networks",
      406,
      { detail: "currency_code is required" },
      errors.ExchangeError,
    ],
    ["public_get_mkt_tickers", 500, "<html>oops</html>", errors.ExchangeNotAvailable],
    ["public_get_mkt_tickers", 503, null, errors.ExchangeNotAvailable],
    ["public_get_mkt_tickers", 418, null, errors.ExchangeError],
  ] as const)("%s %i → class", (endpointId, status, raw, expected) => {
    const error = mapError(endpointId, status, raw);
    expect(error.constructor).toBe(expected);
    expect(error.status).toBe(status);
    expect(error.body).toEqual(raw);
    expect(error.endpointId).toBe(endpointId);
  });

  it("parses retry-after", () => {
    const fromBody = mapError("public_get_mkt_tickers", 429, {
      detail: "Expected available in 86398 seconds.",
    });
    expect(fromBody).toBeInstanceOf(errors.RateLimitExceeded);
    expect((fromBody as errors.RateLimitExceeded).retryAfter).toBe(86398);
    expect((mapError("x", 429, {}, "12") as errors.RateLimitExceeded).retryAfter).toBe(12);
    expect((mapError("x", 429, null, "soon") as errors.RateLimitExceeded).retryAfter).toBeNull();
  });

  it("exposes OTP codes and messages", () => {
    const otp = mapError("private_post_wlt_withdraws_verify_otp_id", 400, {
      code: "extra_try",
    }) as errors.InvalidOTP;
    expect(otp.code).toBe("extra_try");
    expect(
      mapError("private_post_odr_orders", 406, { detail: "insufficent_balance" }).message,
    ).toBe("406 private_post_odr_orders: insufficent_balance");
    expect(mapError("x", 500, null).message).toBe("500 x");
  });

  it("follows the ccxt hierarchy", () => {
    for (const cls of [
      errors.AuthenticationError,
      errors.PermissionDenied,
      errors.InsufficientFunds,
      errors.InvalidOrder,
      errors.OrderNotFound,
      errors.BadRequest,
      errors.NotSupported,
    ]) {
      expect(new cls("x")).toBeInstanceOf(errors.ExchangeError);
    }
    for (const cls of [
      errors.RateLimitExceeded,
      errors.RequestTimeout,
      errors.ExchangeNotAvailable,
    ]) {
      expect(new cls("x")).toBeInstanceOf(errors.NetworkError);
    }
    expect(new errors.BadSymbol("x")).toBeInstanceOf(errors.BadRequest);
    expect(new errors.InvalidOTP("x")).toBeInstanceOf(errors.BadRequest);
    expect(new errors.NetworkError("x")).toBeInstanceOf(errors.BitpinError);
    expect(new errors.BadSymbol("x").name).toBe("BadSymbol");
  });

  it("not supported is bilingual", () => {
    const error = notSupported("editOrder");
    expect(error).toBeInstanceOf(errors.NotSupported);
    expect(error.message).toContain("Cancel the order");
    expect(error.message).toContain("ویرایش");
    expect(error.feature).toBe("editOrder");
  });
});

describe("request building", () => {
  const config = resolveConfig({});

  it("puts GET params in the query", () => {
    const req = buildRequest(
      config,
      "private_get_odr_orders",
      {},
      { symbol: "BTC_IRT", state: ["active", "initial"], limit: 50, side: undefined, end: null },
    );
    expect(req.method).toBe("GET");
    expect(req.url).toBe("https://api.bitpin.org/api/v1/odr/orders/");
    expect(req.params).toEqual({ symbol: "BTC_IRT", state: "active,initial", limit: "50" });
    expect(req.body).toBeUndefined();
    expect(req.auth).toBe("private");
    expect(req.buckets).toEqual(["order_read"]);
    expect(req.idempotent).toBe(true);
  });

  it("formats bodies exactly", () => {
    const req = buildRequest(config, "private_post_odr_orders", {}, undefined, {
      symbol: "BTC_IRT",
      base_amount: new Decimal("1E-8"),
      price: 3100000000,
      stop_price: undefined,
      flag: false,
      nested: [{ a: 0.1 }],
    });
    expect(req.body).toEqual({
      symbol: "BTC_IRT",
      base_amount: "0.00000001",
      price: "3100000000",
      flag: false,
      nested: [{ a: "0.1" }],
    });
    expect(req.params).toBeUndefined();
    expect(req.idempotent).toBe(false);
    const q = buildRequest(
      config,
      "public_get_mkt_networks",
      {},
      { can_deposit: true, x: new Decimal("1.50") },
    );
    expect(q.params).toEqual({ can_deposit: "true", x: "1.5" });
  });

  it("encodes path params and checks them", () => {
    const req = buildRequest(config, "private_delete_odr_orders_identifier_identifier", {
      identifier: "a b/c",
    });
    expect(req.url).toBe("https://api.bitpin.org/api/v1/odr/orders/identifier/a%20b%2Fc/");
    expect(() => buildRequest(config, "public_get_mth_orderbook_symbol")).toThrow(
      /missing path parameter 'symbol'/,
    );
    expect(() => buildRequest(config, "public_get_nope")).toThrow(/unknown endpoint/);
    expect(
      buildRequest(
        resolveConfig({ restUrl: "https://api.bitpin.market/" }),
        "public_get_mkt_tickers",
      ).url,
    ).toBe("https://api.bitpin.market/api/v1/mkt/tickers/");
    expect(
      buildRequest(config, "private_post_odr_orders_bulk", {}, undefined, [
        { price: new Decimal("1.50") },
      ]).body,
    ).toEqual([{ price: "1.5" }]);
  });
});
