/**
 * `Bitpin`: the Bitpin exchange client for TypeScript and JavaScript.
 *
 * Unified methods use ccxt names and return ccxt structures with Decimal numbers. Every
 * endpoint in the spec is also an implicit method, e.g. `await client.publicGetMktTickers()`.
 */
import { type BitpinOptions, type ResolvedConfig, resolveConfig } from "./config.js";
import { TokenState } from "./core/auth.js";
import { mapError, notSupported } from "./core/errors.js";
import { Decimal, type Numeric, toDecimal } from "./core/numbers.js";
import * as parse from "./core/parse.js";
import { SlidingWindowLimiter } from "./core/ratelimit.js";
import { type BuiltRequest, buildRequest } from "./core/request.js";
import { toMarketId, toSymbol } from "./core/symbols.js";
import * as errors from "./errors.js";
import { CONSTANTS, ENDPOINTS, HAS, type ImplicitApi, URLS } from "./generated/spec.js";
import { keyId, MemoryTokenStore, type TokenStore } from "./tokenStore.js";
import type {
  Balances,
  BankAccount,
  CancelResult,
  Currency,
  DepositAddress,
  Info,
  Market,
  Network,
  OHLCV,
  Order,
  OrderBook,
  Ticker,
  Trade,
  TradingFee,
  Transaction,
} from "./types.js";
import { VERSION } from "./version.js";
import type { BitpinWS, TransportFactory } from "./ws/client.js";

/** ccxt timeframe → seconds. Bitpin's candle resolutions use the same names. */
export const TIMEFRAMES: Record<string, number> = {
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "30m": 1800,
  "1h": 3600,
  "3h": 10800,
  "4h": 14400,
  "6h": 21600,
  "1d": 86400,
  "1w": 604800,
  "1M": 2592000,
};
const MAX_RATE_LIMIT_WAIT = 5;
const DEFAULT_OHLCV_LIMIT = 500;
const ORDER_TYPES = ["limit", "market", "stop_limit", "oco"];
const PARAM_ALIASES: Record<string, string> = {
  clientOrderId: "identifier",
  stopPrice: "stop_price",
  triggerPrice: "stop_price",
  takeProfitPrice: "oco_target_price",
  ocoTargetPrice: "oco_target_price",
  quoteAmount: "quote_amount",
  cost: "quote_amount",
};
const MAX_PAGE_SIZE: Record<string, keyof typeof CONSTANTS> = {
  private_get_odr_orders: "orders_max_page_size",
  private_get_odr_fills: "fills_max_page_size",
  private_get_wlt_wallets: "wallets_max_page_size",
  private_get_wlt_deposits: "wallet_lists_max_page_size",
  private_get_wlt_withdraws: "wallet_lists_max_page_size",
};

export type Params = Record<string, unknown>;
export interface OrderRequest {
  symbol: string;
  type: string;
  side: string;
  amount?: Numeric | null;
  price?: Numeric | null;
  params?: Params;
}

// Implicit methods are assigned in the constructor; this interface gives them types.
export interface Bitpin extends ImplicitApi {}

// biome-ignore lint/suspicious/noUnsafeDeclarationMerging: see above
export class Bitpin {
  readonly id = "bitpin";
  readonly name = "Bitpin";
  readonly has: Readonly<Record<string, boolean>> = HAS;
  readonly timeframes: Readonly<Record<string, string>> = Object.fromEntries(
    Object.keys(TIMEFRAMES).map((t) => [t, t]),
  );
  readonly config: ResolvedConfig;
  markets: Record<string, Market> = {};
  marketsById: Record<string, Market> = {};

  private readonly fetchImpl: typeof fetch;
  private readonly clock: () => number;
  private readonly sleep: (seconds: number) => Promise<void>;
  private readonly limiter: SlidingWindowLimiter;
  private readonly tokens: TokenState;
  private readonly store: TokenStore;
  private storeLoaded = false;
  private storeKey: string | null = null;
  private authLock: Promise<unknown> = Promise.resolve();
  private readonly wsTransport: TransportFactory | undefined;
  private ws: BitpinWS | null = null;

  constructor(options: BitpinOptions = {}) {
    this.config = resolveConfig(options, typeof process === "undefined" ? {} : process.env);
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.clock = options.clock ?? (() => Date.now() / 1000);
    this.sleep = options.sleep ?? ((s) => new Promise((resolve) => setTimeout(resolve, s * 1000)));
    this.limiter = new SlidingWindowLimiter(this.config.allRateLimits(), this.clock);
    this.tokens = new TokenState(this.clock);
    this.store = options.tokenStore ?? new MemoryTokenStore();
    this.wsTransport = options.wsTransport as TransportFactory | undefined;
    for (const endpoint of Object.values(ENDPOINTS)) {
      (this as any)[endpoint.implicit] = (params?: Params, body?: unknown) =>
        this.implicit(endpoint.id, params, body);
    }
  }

  toString(): string {
    return `Bitpin(${String(this.config)})`;
  }

  toJSON(): unknown {
    return { id: this.id, config: this.config };
  }

  /** Close the WebSocket connection, if one was opened. */
  async close(): Promise<void> {
    const ws = this.ws;
    this.ws = null;
    await ws?.close();
  }

  /** ccxt-style description: urls, capabilities, timeframes and effective rate limits. */
  describe(): Record<string, any> {
    return {
      id: this.id,
      name: this.name,
      urls: { api: this.config.restUrl, ws: this.config.wsUrl, doc: URLS.docs },
      has: { ...this.has },
      timeframes: { ...this.timeframes },
      rateLimits: Object.fromEntries(
        Object.entries(this.config.allRateLimits()).map(([name, rule]) => [
          name,
          `${rule.limit}/${rule.period}`,
        ]),
      ),
    };
  }

  // --- transport -------------------------------------------------------------------------

  private implicit(endpointId: string, params?: Params, body?: unknown): Promise<any> {
    const endpoint = ENDPOINTS[endpointId]!;
    const values = { ...(params ?? {}) };
    const pathParams: Params = {};
    for (const key of Object.keys(values)) {
      if (endpoint.path.includes(`{${key}}`)) {
        pathParams[key] = values[key];
        delete values[key];
      }
    }
    if (endpoint.method === "GET") return this.request(endpointId, pathParams, values);
    return this.request(endpointId, pathParams, undefined, body ?? values);
  }

  /** Call one endpoint: rate limit, authenticate, send, map errors, retry if safe. */
  async request(
    endpointId: string,
    pathParams: Params = {},
    params?: Params,
    body?: unknown,
  ): Promise<any> {
    const req = buildRequest(this.config, endpointId, pathParams, params, body);
    let reauthenticated = false;
    let attempt = 0;
    for (;;) {
      const token = req.auth === "private" ? await this.accessToken() : null;
      try {
        return await this.send(req, token);
      } catch (error) {
        if (error instanceof errors.AuthenticationError) {
          if (req.auth !== "private" || reauthenticated) throw error;
          reauthenticated = true;
          this.tokens.expireAccess(token ?? undefined);
          continue;
        }
        if (error instanceof errors.NetworkError) {
          const wait = this.retryDelay(req, error, attempt);
          if (wait === null) throw error;
          attempt += 1;
          await this.sleep(wait);
          continue;
        }
        throw error;
      }
    }
  }

  private retryDelay(
    req: BuiltRequest,
    error: errors.NetworkError,
    attempt: number,
  ): number | null {
    if (!req.idempotent || attempt >= this.config.maxRetries) return null;
    if (error instanceof errors.RateLimitExceeded) {
      if (error.retryAfter === null || error.retryAfter > MAX_RATE_LIMIT_WAIT) return null;
      return error.retryAfter;
    }
    return 0.5 * 2 ** attempt;
  }

  private async send(req: BuiltRequest, token: string | null): Promise<any> {
    if (this.config.enableRateLimit) {
      const wait = this.limiter.reserve(req.buckets);
      if (wait > 0) await this.sleep(wait);
    }
    const headers: Record<string, string> = {
      Accept: "application/json",
      "User-Agent": this.config.userAgent ?? `bitpin-sdk-ts/${VERSION}`,
    };
    if (token !== null) headers.Authorization = `Bearer ${token}`;
    if (req.body !== undefined) headers["Content-Type"] = "application/json";
    const url = req.params ? `${req.url}?${new URLSearchParams(req.params)}` : req.url;
    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method: req.method,
        headers,
        body: req.body === undefined ? undefined : JSON.stringify(req.body),
        signal: AbortSignal.timeout(this.config.timeout),
      });
    } catch (cause) {
      const timeout =
        cause instanceof Error && (cause.name === "TimeoutError" || cause.name === "AbortError");
      const Kind = timeout ? errors.RequestTimeout : errors.NetworkError;
      const reason = timeout
        ? "request timed out"
        : cause instanceof Error
          ? cause.name
          : "network error";
      // The cause of a credentials request may hold its body, which has the secret key.
      const details =
        req.auth === "credentials"
          ? { endpointId: req.endpointId }
          : { endpointId: req.endpointId, cause };
      throw new Kind(`${req.endpointId}: ${reason}`, details);
    }
    const text = await response.text();
    let data: unknown;
    let valid = true;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      valid = false;
      data = text;
    }
    if (response.status >= 400) {
      throw mapError(req.endpointId, response.status, data, response.headers.get("retry-after"));
    }
    if (!valid) {
      throw new errors.ExchangeError(`${req.endpointId}: invalid JSON in response`, {
        status: response.status,
        body: text,
        endpointId: req.endpointId,
      });
    }
    return data;
  }

  // --- authentication ----------------------------------------------------------------------

  /** @internal */
  credentials(): { api_key: string; secret_key: string } {
    if (!this.config.hasCredentials) {
      throw new errors.AuthenticationError(
        "apiKey and secretKey are required for private endpoints",
      );
    }
    return { api_key: this.config.apiKey!, secret_key: this.config.secretKey! };
  }

  private withAuthLock<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.authLock.then(fn);
    this.authLock = run.catch(() => undefined);
    return run;
  }

  private accessToken(): Promise<string> {
    return this.withAuthLock(async () => {
      const credentials = this.credentials();
      this.storeKey ??= await keyId(credentials.api_key); // PBKDF2 is slow on purpose
      if (!this.storeLoaded) {
        this.storeLoaded = true;
        const stored = await this.store.load(this.storeKey);
        if (stored) this.tokens.load(stored);
      }
      let action = this.tokens.action();
      if (action === "refresh" && this.tokens.tokens) {
        const refresh = buildRequest(
          this.config,
          "credentials_post_usr_refresh_token",
          {},
          undefined,
          {
            refresh: this.tokens.tokens.refresh,
          },
        );
        try {
          await this.store.save(
            this.storeKey,
            this.tokens.setAccess(await this.send(refresh, null)),
          );
          action = "ok";
        } catch (error) {
          if (!(error instanceof errors.AuthenticationError || error instanceof errors.BadRequest))
            throw error;
          action = "authenticate";
        }
      }
      if (action === "authenticate") {
        const login = buildRequest(
          this.config,
          "credentials_post_usr_authenticate",
          {},
          undefined,
          credentials,
        );
        await this.store.save(this.storeKey, this.tokens.setTokens(await this.send(login, null)));
      }
      return this.tokens.accessToken!;
    });
  }

  // --- markets -----------------------------------------------------------------------------

  async fetchMarkets(): Promise<Market[]> {
    return ((await this.request("public_get_mkt_markets")) as Info[]).map(parse.parseMarket);
  }

  /** Fetch markets once and cache them in `markets` and `marketsById`. */
  async loadMarkets(reload = false): Promise<Record<string, Market>> {
    if (reload || !Object.keys(this.markets).length) {
      const markets = await this.fetchMarkets();
      this.markets = Object.fromEntries(markets.map((m) => [m.symbol, m]));
      this.marketsById = Object.fromEntries(markets.map((m) => [m.id, m]));
    }
    return this.markets;
  }

  /** The cached market for `BTC/IRT` or `BTC_IRT`. Call `loadMarkets()` first. */
  market(symbol: string): Market {
    if (!Object.keys(this.markets).length)
      throw new errors.BitpinError("markets not loaded; call loadMarkets() first");
    const id = toMarketId(symbol);
    const market = this.marketsById[id];
    if (!market) throw new errors.BadSymbol(`unknown market ${toSymbol(id)}`);
    return market;
  }

  async fetchCurrencies(): Promise<Record<string, Currency>> {
    const rows = (await this.request("public_get_mkt_currencies")) as Info[];
    return Object.fromEntries(rows.map(parse.parseCurrency).map((c) => [c.code, c]));
  }

  /** All networks. `params`: `code`, `can_deposit`, `can_withdraw`. */
  async fetchNetworks(params?: Params): Promise<Network[]> {
    return ((await this.request("public_get_mkt_networks", {}, params)) as Info[]).map(
      parse.parseNetwork,
    );
  }

  /** `{symbol: suspended}` for your account. Limited to 2 requests per minute. */
  async fetchMarketSuspensions(): Promise<Record<string, boolean>> {
    const rows = (await this.request("private_get_mkt_markets_suspensions")) as Info[];
    return Object.fromEntries(rows.map((r) => [toSymbol(String(r.code)), Boolean(r.suspended)]));
  }

  // --- tickers, order book, trades, candles -------------------------------------------------

  async fetchTickers(symbols?: string[]): Promise<Record<string, Ticker>> {
    const rows = (await this.request("public_get_mkt_tickers")) as Info[];
    const tickers = Object.fromEntries(rows.map(parse.parseTicker).map((t) => [t.symbol, t]));
    if (!symbols) return tickers;
    const wanted = new Set(symbols.map((s) => toSymbol(toMarketId(s))));
    return Object.fromEntries(Object.entries(tickers).filter(([s]) => wanted.has(s)));
  }

  async fetchTicker(symbol: string): Promise<Ticker> {
    const unified = toSymbol(toMarketId(symbol));
    const ticker = (await this.fetchTickers([unified]))[unified];
    if (!ticker) throw new errors.BadSymbol(`no ticker for ${unified}`);
    return ticker;
  }

  /** Top of the book (default 20 levels, at most 50). */
  async fetchOrderBook(symbol: string, limit?: number): Promise<OrderBook> {
    if (limit !== undefined && limit > CONSTANTS.orderbook_max_limit) {
      throw new errors.BadRequest(`order book limit is at most ${CONSTANTS.orderbook_max_limit}`);
    }
    const id = toMarketId(symbol);
    const raw = await this.request("public_get_mth_orderbook_symbol", { symbol: id }, { limit });
    return parse.parseOrderBook(raw, toSymbol(id));
  }

  /** Recent public trades, oldest first. `since` (ms) and `limit` filter client-side. */
  async fetchTrades(symbol: string, since?: number, limit?: number): Promise<Trade[]> {
    const id = toMarketId(symbol);
    const rows = (await this.request("public_get_mth_matches_symbol", { symbol: id })) as Info[];
    const trades = rows
      .map((r) => parse.parseTrade(r, toSymbol(id)))
      .sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0));
    const filtered = trades.filter((t) => since === undefined || (t.timestamp ?? 0) >= since);
    return limit ? filtered.slice(-limit) : filtered;
  }

  /** Candles `[ms, open, high, low, close, volume]`, oldest first. Without `since`: the latest `limit` (500). */
  async fetchOHLCV(
    symbol: string,
    timeframe = "30m",
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<OHLCV[]> {
    const step = TIMEFRAMES[timeframe];
    if (step === undefined) {
      throw new errors.BadRequest(
        `timeframe '${timeframe}' is not supported; use one of ${Object.keys(TIMEFRAMES).join(", ")}`,
      );
    }
    if (limit !== undefined && limit < 1)
      throw new errors.BadRequest("fetchOHLCV limit must be at least 1");
    const count = limit ?? DEFAULT_OHLCV_LIMIT;
    if (count > CONSTANTS.candles_max_per_request) {
      throw new errors.BadRequest(
        `at most ${CONSTANTS.candles_max_per_request} candles per request`,
      );
    }
    const start =
      since === undefined ? Math.floor(this.clock()) - count * step : Math.floor(since / 1000);
    const end = since === undefined ? Math.floor(this.clock()) : start + count * step;
    const rows = (await this.request(
      "public_get_mkt_candles",
      {},
      {
        symbol: toMarketId(symbol),
        res: timeframe,
        from: start,
        to: end,
        ...params,
      },
    )) as Info[];
    const candles = rows.map(parse.parseOhlcv);
    return since === undefined ? candles.slice(-count) : candles.slice(0, count);
  }

  /** Alias with ccxt Python's spelling. */
  fetchOhlcv(
    symbol: string,
    timeframe = "30m",
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<OHLCV[]> {
    return this.fetchOHLCV(symbol, timeframe, since, limit, params);
  }

  /** Your maker/taker fees per market, as ratios (0.003 = 0.3 %). */
  async fetchTradingFees(): Promise<Record<string, TradingFee>> {
    const rows = (await this.request("private_get_mkt_commissions")) as Info[];
    return Object.fromEntries(rows.map(parse.parseTradingFee).map((f) => [f.symbol, f]));
  }

  async fetchTradingFee(symbol: string): Promise<TradingFee> {
    const unified = toSymbol(toMarketId(symbol));
    const fee = (await this.fetchTradingFees())[unified];
    if (!fee) throw new errors.BadSymbol(`no trading fee for ${unified}`);
    return fee;
  }

  // --- orders ----------------------------------------------------------------------------------

  /**
   * Place an order. `type`: limit, market, stop_limit or oco. `params`: `clientOrderId`,
   * `quoteAmount` (market by quote), `stopPrice`/`triggerPrice`, `takeProfitPrice` (oco).
   */
  async createOrder(
    symbol: string,
    type: string,
    side: string,
    amount?: Numeric | null,
    price?: Numeric | null,
    params?: Params,
  ): Promise<Order> {
    const body = orderBody(symbol, type, side, amount, price, params);
    return parse.parseOrder(await this.request("private_post_odr_orders", {}, undefined, body));
  }

  /** Place up to 10 orders in one atomic request. */
  async createOrders(orders: OrderRequest[]): Promise<Order[]> {
    if (!orders.length) throw new errors.BadRequest("createOrders needs at least one order");
    if (orders.length > CONSTANTS.bulk_orders_max) {
      throw new errors.BadRequest(`createOrders takes at most ${CONSTANTS.bulk_orders_max} orders`);
    }
    const body = orders.map((o) =>
      orderBody(o.symbol, o.type, o.side, o.amount, o.price, o.params),
    );
    return parse.parseBulkOrders(
      await this.request("private_post_odr_orders_bulk", {}, undefined, body),
    );
  }

  async fetchOrder(id: string | number, _symbol?: string): Promise<Order> {
    return parse.parseOrder(await this.request("private_get_odr_orders_id", { id }));
  }

  /** Active orders and orders closed in the last 7 days, oldest first. `params.paginate` reads every page. */
  async fetchOrders(
    symbol?: string,
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<Order[]> {
    const query = { symbol: symbol ? toMarketId(symbol) : undefined, start: iso(since), limit };
    const rows = await this.paged("private_get_odr_orders", query, params);
    return rows
      .map(parse.parseOrder)
      .sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0) || Number(a.id) - Number(b.id));
  }

  fetchOpenOrders(
    symbol?: string,
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<Order[]> {
    return this.fetchOrders(symbol, since, limit, { ...params, state: ["initial", "active"] });
  }

  /** Closed orders from the last 7 days. Older ones: `fetchOrderHistory()`. */
  fetchClosedOrders(
    symbol?: string,
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<Order[]> {
    return this.fetchOrders(symbol, since, limit, { ...params, state: "closed" });
  }

  /** Ask the engine to cancel; the order closes a moment later. */
  async cancelOrder(
    id: string | number,
    _symbol?: string,
  ): Promise<{ id: string; clientOrderId: null; info: null }> {
    await this.request("private_delete_odr_orders_id", { id });
    return { id: String(id), clientOrderId: null, info: null };
  }

  /** Cancel by your `clientOrderId`. */
  async cancelOrderByIdentifier(
    identifier: string,
  ): Promise<{ id: null; clientOrderId: string; info: null }> {
    await this.request("private_delete_odr_orders_identifier_identifier", { identifier });
    return { id: null, clientOrderId: identifier, info: null };
  }

  /** Cancel up to 10 orders, by `ids` or by `identifiers` (not both). */
  async cancelOrders(options: {
    ids?: (string | number)[];
    identifiers?: string[];
  }): Promise<CancelResult> {
    const { ids, identifiers } = options;
    if ((ids === undefined) === (identifiers === undefined)) {
      throw new errors.BadRequest("cancelOrders needs exactly one of ids or identifiers");
    }
    const values = (ids ?? identifiers ?? []).map(String);
    if (values.length > CONSTANTS.bulk_orders_max) {
      throw new errors.BadRequest(`cancelOrders takes at most ${CONSTANTS.bulk_orders_max} orders`);
    }
    const raw = await this.request("private_delete_odr_orders_bulk", {}, undefined, {
      [ids ? "ids" : "identifiers"]: values,
    });
    return {
      canceled: (raw?.canceled_orders ?? []).map(String),
      notCanceled: (raw?.not_canceled_orders ?? []).map(String),
      info: raw,
    };
  }

  /** Your fills from the last 24 hours, oldest first. */
  async fetchMyTrades(
    symbol?: string,
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<Trade[]> {
    if (since !== undefined && since < (this.clock() - CONSTANTS.fills_max_age_seconds) * 1000) {
      throw new errors.BadRequest("fetchMyTrades only covers the last 24 hours");
    }
    const query = {
      symbol: symbol ? toMarketId(symbol) : undefined,
      start: since === undefined ? undefined : Math.floor(since / 1000),
      limit,
    };
    const rows = await this.paged("private_get_odr_fills", query, params);
    return rows
      .map(parse.parseMyTrade)
      .sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0) || Number(a.id) - Number(b.id));
  }

  /** Closed orders with at least one fill, newest first; range at most 90 days. `params.paginate` follows the cursor. */
  async fetchOrderHistory(
    symbol?: string,
    since?: number,
    until?: number,
    limit?: number,
    params?: Params,
  ): Promise<Order[]> {
    const max = CONSTANTS.order_history_max_limit;
    if (limit !== undefined && (limit < 1 || limit > max))
      throw new errors.BadRequest(`order history limit must be 1..${max}`);
    if (since !== undefined && until !== undefined) {
      if (since >= until) throw new errors.BadRequest("order history since must be before until");
      if (until - since > CONSTANTS.order_history_max_range_days * 86_400_000) {
        throw new errors.BadRequest("order history range is at most 90 days");
      }
    }
    const { paginate, ...extra } = params ?? {};
    const filters = { symbol: symbol ? toMarketId(symbol) : undefined, limit, ...extra };
    let query: Params = { ...filters, start: since, end: until };
    const orders: Order[] = [];
    const seenIds = new Set<string>();
    const seenCursors = new Set<string>();
    for (;;) {
      const raw = await this.request("private_get_odr_order_history", {}, query);
      for (const row of raw?.results ?? []) {
        const order = parse.parseHistoryOrder(row);
        if (!seenIds.has(order.id)) {
          seenIds.add(order.id);
          orders.push(order);
        }
      }
      const cursor = raw?.next_cursor;
      if (!(paginate && raw?.has_next && cursor) || seenCursors.has(cursor)) return orders;
      seenCursors.add(cursor);
      // The cursor replaces start/end; the server doesn't keep the other filters.
      query = { ...filters, cursor };
    }
  }

  // --- wallet ------------------------------------------------------------------------------

  /** Balances of the `main` wallet (`params.service` for others). */
  async fetchBalance(params?: Params): Promise<Balances> {
    const rows = await this.allPages("private_get_wlt_wallets", {
      service: "main",
      limit: CONSTANTS.wallets_max_page_size,
      ...params,
    });
    return parse.parseBalance(rows);
  }

  /** Your bank accounts. Use an `id` as `accountNumber` when withdrawing IRT. */
  async fetchBankAccounts(): Promise<BankAccount[]> {
    return ((await this.request("private_get_wlt_account_numbers")) as Info[]).map(
      parse.parseBankAccount,
    );
  }

  /** Your deposit address for `code` on `network` (created on first use). */
  async fetchDepositAddress(
    code: string,
    network?: string,
    params?: Params,
  ): Promise<DepositAddress> {
    const net = network ?? (params?.network as string | undefined);
    if (!net) throw new errors.BadRequest("fetchDepositAddress needs a network code, e.g. 'TRX'");
    const body = { currency: code.toUpperCase(), network: net.toUpperCase() };
    return parse.parseDepositAddress(
      await this.request("private_post_wlt_address", {}, undefined, body),
      body.network,
    );
  }

  /** Networks of one currency, with deposit/withdraw availability. */
  async fetchCurrencyNetworks(code: string): Promise<Network[]> {
    const rows = (await this.request(
      "private_get_wlt_networks",
      {},
      { currency_code: code.toUpperCase() },
    )) as Info[];
    return rows.map(parse.parseCurrencyNetwork);
  }

  async fetchDeposits(
    code?: string,
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<Transaction[]> {
    const query = { currency: code?.toUpperCase(), start: iso(since), limit };
    return (await this.paged("private_get_wlt_deposits", query, params)).map(parse.parseDeposit);
  }

  /** `since` is applied per day. */
  async fetchWithdrawals(
    code?: string,
    since?: number,
    limit?: number,
    params?: Params,
  ): Promise<Transaction[]> {
    const query = { currency: code?.toUpperCase(), start: iso(since)?.slice(0, 10), limit };
    return (await this.paged("private_get_wlt_withdraws", query, params)).map(
      parse.parseWithdrawal,
    );
  }

  /**
   * Create a withdrawal. It is not sent until confirmed with `verifyWithdrawOtp()` (twice
   * unless `info.is_single_otp`). Crypto: `address` + `params.network`; IRT:
   * `params.accountNumber`; internal transfer: `params.alternativeAddress`.
   */
  async withdraw(
    code: string,
    amount: Numeric,
    address?: string | null,
    tag?: string | null,
    params?: Params,
  ): Promise<Transaction> {
    const {
      network,
      accountNumber,
      account_number,
      alternativeAddress,
      alternative_address,
      ...extra
    } = params ?? {};
    if (!(toDecimal(amount) ?? new Decimal(0)).gt(0))
      throw new errors.BadRequest("withdraw amount must be positive");
    const account = accountNumber ?? account_number;
    const alternative = alternativeAddress ?? alternative_address;
    const body: Params = { currency: code.toUpperCase(), amount };
    if (alternative) body.alternative_address = alternative;
    else if (account !== undefined && account !== null) body.account_number = String(account);
    else if (address) {
      if (!network) throw new errors.BadRequest("crypto withdrawals need params.network");
      body.address = address;
      body.network = String(network).toUpperCase();
      if (tag) body.memo = tag;
    } else {
      throw new errors.BadRequest(
        "withdraw needs an address, params.accountNumber or params.alternativeAddress",
      );
    }
    Object.assign(body, extra);
    return parse.parseWithdrawal(
      await this.request("private_post_wlt_withdraws", {}, undefined, body),
    );
  }

  /** Confirm a withdrawal. First OTP: your authenticator app. Second: the code sent to you. */
  verifyWithdrawOtp(id: string | number, otp: string, second = false): Promise<Info> {
    return this.request("private_post_wlt_withdraws_verify_otp_id", { id }, undefined, {
      otp,
      is_second_otp: second,
    });
  }

  /** Send the OTP of a withdrawal in the `initial` state again. */
  resendWithdrawOtp(id: string | number, first = true, voiceCall = false): Promise<Info> {
    return this.request("private_post_wlt_withdraws_retry_id", { id }, undefined, {
      first,
      use_voice_call: voiceCall,
    });
  }

  // --- pagination ----------------------------------------------------------------------------

  private async paged(endpointId: string, query: Params, params?: Params): Promise<Info[]> {
    const { paginate, maxPages, ...merged } = { ...query, ...params };
    if (paginate) return this.allPages(endpointId, { ...merged, maxPages });
    return (await this.request(endpointId, {}, merged)) as Info[];
  }

  /** Walk an id-cursor list: `offset` means "ids below this", not a row count. */
  private async allPages(endpointId: string, input: Params): Promise<Info[]> {
    const { maxPages, ...query } = input;
    if (query.limit === undefined || query.limit === null)
      query.limit = CONSTANTS[MAX_PAGE_SIZE[endpointId]!];
    const limit = Number(query.limit);
    const rows: Info[] = [];
    let offset: number | null = null;
    for (let page = 0; page < Number(maxPages ?? 100); page++) {
      const batch = (await this.request(endpointId, {}, query)) as Info[];
      if (!batch.length) break;
      const lowest = Math.min(...batch.map((r) => Number(r.id)));
      if (offset !== null && lowest >= offset) break; // the server didn't move past the last page
      rows.push(...batch);
      if (batch.length < limit) break;
      offset = lowest;
      query.offset = lowest;
    }
    return rows;
  }

  // --- websocket -------------------------------------------------------------------------------

  private async websocket(): Promise<BitpinWS> {
    if (!this.ws) {
      const { BitpinWS } = await import("./ws/client.js");
      this.ws ??= new BitpinWS(this, { transport: this.wsTransport });
    }
    return this.ws;
  }

  /** Wait for the next 24h ticker update of `symbol`. */
  async watchTicker(symbol: string): Promise<Ticker> {
    return (await this.websocket()).watchTicker(symbol);
  }

  /** Wait for the next candles of `timeframe`. */
  async watchOHLCV(symbol: string, timeframe = "1m"): Promise<OHLCV[]> {
    return (await this.websocket()).watchOHLCV(symbol, timeframe);
  }

  /** Wait for the next order-book update of `symbol`. */
  async watchOrderBook(symbol: string): Promise<OrderBook> {
    return (await this.websocket()).watchOrderBook(symbol);
  }

  /** Wait for the next public trades of `symbol`. */
  async watchTrades(symbol: string): Promise<Trade[]> {
    return (await this.websocket()).watchTrades(symbol);
  }

  /** Wait for the next update of one of your orders. */
  async watchOrders(symbol?: string): Promise<Order> {
    return (await this.websocket()).watchOrders(symbol);
  }

  /** Wait for your next fill. */
  async watchMyTrades(symbol?: string): Promise<Trade> {
    return (await this.websocket()).watchMyTrades(symbol);
  }

  // --- not offered by Bitpin yet -----------------------------------------------------------------

  async cancelAllOrders(..._args: unknown[]): Promise<never> {
    throw notSupported("cancelAllOrders");
  }
  async editOrder(..._args: unknown[]): Promise<never> {
    throw notSupported("editOrder");
  }
  async fetchAccounts(..._args: unknown[]): Promise<never> {
    throw notSupported("fetchAccounts");
  }
  async fetchLedger(..._args: unknown[]): Promise<never> {
    throw notSupported("fetchLedger");
  }
  async transfer(..._args: unknown[]): Promise<never> {
    throw notSupported("transfer");
  }
  async fetchDepositWithdrawFees(..._args: unknown[]): Promise<never> {
    throw notSupported("fetchDepositWithdrawFees");
  }
  async fetchPositions(..._args: unknown[]): Promise<never> {
    throw notSupported("fetchPositions");
  }
  async setLeverage(..._args: unknown[]): Promise<never> {
    throw notSupported("setLeverage");
  }
  async createDepositAddress(..._args: unknown[]): Promise<never> {
    throw notSupported("createDepositAddress");
  }
  async watchBalance(..._args: unknown[]): Promise<never> {
    throw notSupported("watchBalance");
  }
  async watchTickers(..._args: unknown[]): Promise<never> {
    throw notSupported("watchTickers");
  }
  setSandboxMode(_enabled: boolean): never {
    throw notSupported("sandbox");
  }
}

function checkPositive(name: string, value: unknown): void {
  const number = toDecimal(value as Numeric);
  if (number !== null && !number.gt(0)) throw new errors.InvalidOrder(`${name} must be positive`);
}

/** Validate an order locally and build the request body. Throws `InvalidOrder`. */
export function orderBody(
  symbol: string,
  type: string,
  side: string,
  amount?: Numeric | null,
  price?: Numeric | null,
  params?: Params,
): Params {
  if (!ORDER_TYPES.includes(type))
    throw new errors.InvalidOrder(`order type must be one of ${ORDER_TYPES.join(", ")}`);
  if (side !== "buy" && side !== "sell")
    throw new errors.InvalidOrder("order side must be 'buy' or 'sell'");
  const extra: Params = {};
  for (const [key, value] of Object.entries(params ?? {})) {
    const name = PARAM_ALIASES[key] ?? key;
    if (name in extra && String(extra[name]) !== String(value)) {
      throw new errors.InvalidOrder(`params set ${name} twice ('${key}'); pass only one of both`);
    }
    extra[name] = value;
  }
  const body: Params = { symbol: toMarketId(symbol), type, side };
  if (amount !== undefined && amount !== null) body.base_amount = amount;
  if (price !== undefined && price !== null && type !== "market") body.price = price;
  for (const [key, value] of Object.entries(extra))
    if (value !== undefined && value !== null) body[key] = value;
  checkPositive("amount", body.base_amount);
  checkPositive("price", body.price);
  checkPositive("params.stopPrice", body.stop_price);
  checkPositive("params.takeProfitPrice", body.oco_target_price);
  checkPositive("params.quoteAmount", body.quote_amount);

  if (type === "market") {
    if ("base_amount" in body && "quote_amount" in body)
      throw new errors.InvalidOrder("market orders take only one of amount or quoteAmount");
    if (!("base_amount" in body) && !("quote_amount" in body))
      throw new errors.InvalidOrder("market orders need amount or params.quoteAmount");
    return body;
  }
  if (!("base_amount" in body)) throw new errors.InvalidOrder(`${type} orders need an amount`);
  if (!("price" in body)) throw new errors.InvalidOrder(`${type} orders need a price`);
  if ((type === "stop_limit" || type === "oco") && !("stop_price" in body))
    throw new errors.InvalidOrder(`${type} orders need params.stopPrice`);
  if (type === "oco" && !("oco_target_price" in body))
    throw new errors.InvalidOrder("oco orders need params.takeProfitPrice");
  return body;
}

function iso(ms: number | undefined): string | undefined {
  return ms === undefined ? undefined : new Date(ms).toISOString().replace("Z", "+00:00");
}
