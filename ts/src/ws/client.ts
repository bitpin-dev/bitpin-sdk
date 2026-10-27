/**
 * `BitpinWS`: ccxt.pro-style `watch*` methods over Bitpin's Centrifugo server.
 *
 * Each `watch*` call subscribes once (the first time) and resolves with the next update.
 * Every distinct watch (method + symbol + timeframe) has its own queue (`queueSize` updates,
 * oldest dropped first), so a loop doesn't miss any and watchers of different symbols on one
 * channel all see their updates. Two callers awaiting the *same* watch split its updates.
 */
import type { Bitpin } from "../client.js";
import { TIMEFRAMES } from "../client.js";
import { toMarketId } from "../core/symbols.js";
import { AuthenticationError, BadRequest } from "../errors.js";
import { WS_CHANNELS } from "../generated/spec.js";
import type { Info, OHLCV, Order, OrderBook, Ticker, Trade } from "../types.js";
import * as parse from "./parse.js";
import { CentrifugeTransport, type GetToken, type Transport } from "./transport.js";

export type TransportFactory = (url: string, getToken: GetToken | null) => Transport;

class Queue {
  private readonly items: Info[] = [];
  private readonly waiters: ((item: Info) => void)[] = [];
  constructor(
    readonly accept: (data: Info) => boolean,
    private readonly size: number,
  ) {}
  push(item: Info): void {
    const waiter = this.waiters.shift();
    if (waiter) {
      waiter(item);
      return;
    }
    if (this.items.length >= this.size) this.items.shift();
    this.items.push(item);
  }
  next(): Promise<Info> {
    const item = this.items.shift();
    return item ? Promise.resolve(item) : new Promise((resolve) => this.waiters.push(resolve));
  }
}

export class BitpinWS {
  private transport: Transport | null = null;
  private connecting: Promise<Transport> | null = null;
  private readonly channels = new Map<string, Promise<void>>();
  private readonly queues = new Map<string, Queue>();
  private userIdentifier: Promise<string> | null = null;
  private readonly factory: TransportFactory;
  private readonly queueSize: number;

  constructor(
    private readonly client: Bitpin,
    options: { transport?: TransportFactory | undefined; queueSize?: number } = {},
  ) {
    this.factory = options.transport ?? ((url, getToken) => new CentrifugeTransport(url, getToken));
    this.queueSize = options.queueSize ?? 1000;
  }

  async close(): Promise<void> {
    const transport = this.transport;
    this.transport = null;
    this.connecting = null;
    this.channels.clear();
    await transport?.close();
  }

  private async wsInfo(): Promise<Info> {
    return this.client.request(
      "credentials_post_usr_ws_info",
      {},
      undefined,
      this.client.credentials(),
    );
  }

  private connection(): Promise<Transport> {
    this.connecting ??= (async () => {
      const getToken = this.client.config.hasCredentials
        ? async () => String((await this.wsInfo()).ws_token)
        : null;
      const transport = this.factory(this.client.config.wsUrl, getToken);
      await transport.connect();
      this.transport = transport;
      return transport;
    })();
    return this.connecting;
  }

  private onData(channel: string): (data: unknown) => void {
    return (data) => {
      if (!data || typeof data !== "object" || !("event" in data)) return;
      const event = String((data as Info).event);
      for (const [name, queue] of this.queues) {
        const [ch, ev] = JSON.parse(name) as [string, string, string];
        if (ch === channel && ev === event && queue.accept(data as Info)) queue.push(data as Info);
      }
    };
  }

  private async next(
    channel: string,
    event: string,
    key = "",
    accept: (data: Info) => boolean = () => true,
  ): Promise<Info> {
    const name = JSON.stringify([channel, event, key]);
    let queue = this.queues.get(name);
    if (!queue) {
      queue = new Queue(accept, this.queueSize);
      this.queues.set(name, queue);
    }
    if (!this.channels.has(channel)) {
      this.channels.set(
        channel,
        this.connection().then((t) => t.subscribe(channel, this.onData(channel))),
      );
    }
    await this.channels.get(channel);
    return queue.next();
  }

  private async userChannel(): Promise<string> {
    if (!this.client.config.hasCredentials) {
      throw new AuthenticationError("apiKey and secretKey are required for private channels");
    }
    // One lookup shared by every concurrent watcher: ws-info allows 10 requests per minute.
    this.userIdentifier ??= this.wsInfo().then((info) => String(info.user_identifier));
    const identifier = await this.userIdentifier.catch((error) => {
      this.userIdentifier = null;
      throw error;
    });
    return WS_CHANNELS.user_orders.replace("{user_identifier}", identifier);
  }

  async watchTicker(symbol: string): Promise<Ticker> {
    const channel = WS_CHANNELS.market.replace("{symbol}", toMarketId(symbol));
    return parse.parseWsTicker(await this.next(channel, "currency_price_update"));
  }

  /** The latest candles of `timeframe` (Bitpin pushes every 10 s and on trades). */
  async watchOHLCV(symbol: string, timeframe = "1m"): Promise<OHLCV[]> {
    if (!(timeframe in TIMEFRAMES))
      throw new BadRequest(`timeframe '${timeframe}' is not supported`);
    const channel = WS_CHANNELS.market.replace("{symbol}", toMarketId(symbol));
    const accept = (data: Info) =>
      (data.candles ?? []).some((c: Info) => c.resolution === timeframe);
    return parse.parseWsOhlcv(
      await this.next(channel, "candle_update", timeframe, accept),
      timeframe,
    );
  }

  async watchOrderBook(symbol: string): Promise<OrderBook> {
    const channel = WS_CHANNELS.orderbook.replace("{symbol}", toMarketId(symbol));
    return parse.parseWsOrderBook(await this.next(channel, "market_data"));
  }

  async watchTrades(symbol: string): Promise<Trade[]> {
    const channel = WS_CHANNELS.matches.replace("{symbol}", toMarketId(symbol));
    return parse.parseWsTrades(await this.next(channel, "matches_update"));
  }

  /** The next update of one of your orders (created, filled, cancelled). */
  async watchOrders(symbol?: string): Promise<Order> {
    const channel = await this.userChannel();
    const wanted = symbol ? toMarketId(symbol) : null;
    const data = await this.next(
      channel,
      "user_order_update",
      wanted ?? "*",
      (d) => wanted === null || d.symbol === wanted,
    );
    return parse.parseWsOrder(data);
  }

  /** The next fill of one of your orders. */
  async watchMyTrades(symbol?: string): Promise<Trade> {
    const channel = await this.userChannel();
    const wanted = symbol ? toMarketId(symbol) : null;
    const data = await this.next(
      channel,
      "user_match_update",
      wanted ?? "*",
      (d) => wanted === null || d.symbol === wanted,
    );
    return parse.parseWsMyTrade(data);
  }
}
