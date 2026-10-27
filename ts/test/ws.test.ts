import { describe, expect, it } from "vitest";
import { Bitpin, BitpinWS, errors, type GetToken, type Transport } from "../src/index.js";
import { CentrifugeTransport } from "../src/ws/transport.js";
import { body, FakeTime, MockFetch, setup } from "./helpers.js";

class FakeTransport implements Transport {
  connected = 0;
  closed = false;
  token: string | null = null;
  handlers = new Map<string, (data: unknown) => void>();
  constructor(
    readonly url: string,
    readonly getToken: GetToken | null,
  ) {}
  async connect() {
    this.connected++;
    if (this.getToken) this.token = await this.getToken();
  }
  async subscribe(channel: string, onData: (data: unknown) => void) {
    this.handlers.set(channel, onData);
  }
  async close() {
    this.closed = true;
  }
  push(channel: string, data: unknown) {
    this.handlers.get(channel)!(data);
  }
}

const settle = async () => {
  for (let i = 0; i < 30; i++) await new Promise((r) => setImmediate(r));
};

function wsSetup(credentials = true, queueSize?: number) {
  const transports: FakeTransport[] = [];
  const factory = (url: string, getToken: GetToken | null) => {
    const t = new FakeTransport(url, getToken);
    transports.push(t);
    return t;
  };
  const { client, mock } = setup(credentials ? {} : { apiKey: undefined, secretKey: undefined });
  const info = mock.endpoint("credentials_post_usr_ws_info");
  const ws = new BitpinWS(client, { transport: factory, queueSize });
  return { client, ws, transports, info };
}

const TICKER = {
  price: "3145737420",
  change: "0.0258",
  min: "3000000000",
  max: "3200000000",
  mean: "3100000000",
  value: "1500000000000",
  amount: "480.5",
  time: "1760873857000",
  symbol: "BTC_IRT",
  event: "currency_price_update",
};
const candle = { open: "1", close: "2", low: "0.5", high: "3", volume: "10", ts: "1760873760.0" };

describe("websocket", () => {
  it("watchTicker", async () => {
    const { ws, transports } = wsSetup();
    const next = ws.watchTicker("BTC/IRT");
    await settle();
    const t = transports[0]!;
    expect(t.url).toBe("wss://centrifugo.bitpin.org/connection/websocket");
    expect(t.token).toBe(body("credentials_post_usr_ws_info").ws_token);
    t.push("market:BTC_IRT", { event: "candle_update", symbol: "BTC_IRT", candles: [] });
    t.push("market:BTC_IRT", TICKER);
    const ticker = await next;
    expect([
      ticker.symbol,
      ticker.last!.toString(),
      ticker.percentage!.toString(),
      ticker.baseVolume!.toString(),
      ticker.quoteVolume!.toString(),
      ticker.timestamp,
    ]).toEqual(["BTC/IRT", "3145737420", "2.58", "480.5", "1500000000000", 1760873857000]);
    await ws.close();
    expect(t.closed).toBe(true);
  });

  it("subscribes each channel once and ignores junk", async () => {
    const { ws, transports } = wsSetup();
    void ws.watchTicker("BTC/IRT");
    void ws.watchOHLCV("BTC/IRT", "1m");
    const trades = ws.watchTrades("USDT/IRT");
    await settle();
    expect(transports.length).toBe(1);
    expect(transports[0]!.connected).toBe(1);
    expect([...transports[0]!.handlers.keys()].sort()).toEqual([
      "market:BTC_IRT",
      "matches:USDT_IRT",
    ]);
    transports[0]!.push("matches:USDT_IRT", "not a dict");
    transports[0]!.push("matches:USDT_IRT", { no: "event" });
    transports[0]!.push("matches:USDT_IRT", {
      event: "matches_update",
      symbol: "USDT_IRT",
      matches: [
        {
          id: "1_2",
          price: "1",
          base_amount: "2",
          quote_amount: "2",
          side: "buy",
          time: 1760873797.149016,
        },
      ],
    });
    const result = await trades;
    expect([result[0]!.id, result[0]!.timestamp]).toEqual(["1_2", 1760873797149]);
  });

  it("watchOHLCV keeps its timeframe; two timeframes both get updates", async () => {
    const { ws, transports } = wsSetup();
    const one = ws.watchOHLCV("BTC/IRT", "1m");
    const five = ws.watchOHLCV("BTC/IRT", "5m");
    const hour = ws.watchOHLCV("BTC/IRT", "1h");
    await settle();
    transports[0]!.push("market:BTC_IRT", {
      event: "candle_update",
      symbol: "BTC_IRT",
      candles: [
        { ...candle, resolution: "1m" },
        { ...candle, resolution: "5m" },
      ],
    });
    expect((await one)[0]!.map((v) => (v === null ? null : String(v)))).toEqual([
      "1760873760000",
      "1",
      "3",
      "0.5",
      "2",
      "10",
    ]);
    expect((await five).length).toBe(1);
    let done = false;
    void hour.then(() => {
      done = true;
    });
    await settle();
    expect(done).toBe(false);
    transports[0]!.push("market:BTC_IRT", { event: "candle_update", symbol: "BTC_IRT" });
    await expect(ws.watchOHLCV("BTC/IRT", "2h")).rejects.toBeInstanceOf(errors.BadRequest);
  });

  it("watchOrderBook", async () => {
    const { ws, transports } = wsSetup();
    const next = ws.watchOrderBook("BTC_IRT");
    await settle();
    transports[0]!.push("orderbook:BTC_IRT", {
      asks: [
        ["3160000000", "0.2"],
        ["3150000000", "0.01"],
      ],
      bids: [
        ["3130000000", "1"],
        ["3140000000", "0.05"],
      ],
      symbol: "BTC_IRT",
      event_time: "2025-10-19T11:38:27.929164Z",
      event: "market_data",
    });
    const book = await next;
    expect([book.bids[0]![0].toString(), book.asks[0]![0].toString(), book.timestamp]).toEqual([
      "3140000000",
      "3150000000",
      1760873907929,
    ]);
  });

  it("private channels: orders per symbol, fills", async () => {
    const { ws, transports, info } = wsSetup();
    const order = { ...body("private_post_odr_orders"), event: "user_order_update" };
    const btc = ws.watchOrders("BTC/IRT");
    const usdt = ws.watchOrders("USDT/IRT");
    const any = ws.watchOrders();
    await settle();
    const ch = "user:order_info#TESTUSR1";
    transports[0]!.push(ch, { ...order, symbol: "USDT_IRT", id: 2 });
    transports[0]!.push(ch, { ...order, symbol: "BTC_IRT", id: 1 });
    expect((await btc).id).toBe("1");
    expect((await usdt).id).toBe("2");
    expect((await any).id).toBe("2");
    const fill = { ...body("private_get_odr_fills")[0], event: "user_match_update" };
    const mine = ws.watchMyTrades("BTC/IRT");
    const all = ws.watchMyTrades();
    await settle();
    transports[0]!.push(ch, { ...fill, symbol: "USDT_IRT", id: 9 });
    transports[0]!.push(ch, fill);
    expect((await mine).id).toBe("65375307");
    expect((await all).id).toBe("9");
    expect(info.count).toBe(2);
  });

  it("public-only clients connect without a token and refuse private channels", async () => {
    const { ws, transports } = wsSetup(false);
    void ws.watchTrades("BTC/IRT");
    await settle();
    expect(transports[0]!.getToken).toBeNull();
    await expect(ws.watchOrders()).rejects.toBeInstanceOf(errors.AuthenticationError);
    await ws.close();
    await new BitpinWS(new Bitpin({ fetch: new MockFetch().fetch })).close();
  });

  it("drops the oldest update when a queue is full", async () => {
    const { ws, transports } = wsSetup(true, 2);
    void ws.watchTicker("BTC/IRT");
    await settle();
    for (const price of ["0", "1", "2", "3"])
      transports[0]!.push("market:BTC_IRT", { ...TICKER, price });
    expect((await ws.watchTicker("BTC/IRT")).last!.toString()).toBe("2");
    expect((await ws.watchTicker("BTC/IRT")).last!.toString()).toBe("3");
  });

  it("client watch methods delegate and close the socket", async () => {
    const transports: FakeTransport[] = [];
    const mock = new MockFetch();
    mock.endpoint("credentials_post_usr_ws_info");
    mock.endpoint("credentials_post_usr_authenticate");
    const time = new FakeTime();
    const client = new Bitpin({
      apiKey: "k",
      secretKey: "s",
      fetch: mock.fetch,
      clock: time.clock,
      sleep: time.sleep,
      wsTransport: (url: string, getToken: GetToken | null) => {
        const t = new FakeTransport(url, getToken);
        transports.push(t);
        return t;
      },
    });
    const calls = [
      client.watchTicker("BTC/IRT"),
      client.watchOHLCV("BTC/IRT"),
      client.watchOrderBook("BTC/IRT"),
      client.watchTrades("BTC/IRT"),
      client.watchOrders(),
      client.watchMyTrades(),
    ];
    await settle();
    const t = transports[0]!;
    t.push("market:BTC_IRT", TICKER);
    t.push("market:BTC_IRT", {
      event: "candle_update",
      symbol: "BTC_IRT",
      candles: [{ ...candle, resolution: "1m" }],
    });
    t.push("orderbook:BTC_IRT", { asks: [], bids: [], symbol: "BTC_IRT", event: "market_data" });
    t.push("matches:BTC_IRT", { event: "matches_update", symbol: "BTC_IRT", matches: [] });
    t.push("user:order_info#TESTUSR1", {
      ...body("private_post_odr_orders"),
      event: "user_order_update",
    });
    t.push("user:order_info#TESTUSR1", {
      ...body("private_get_odr_fills")[0],
      event: "user_match_update",
    });
    expect((await Promise.all(calls)).length).toBe(6);
    await client.close();
    expect(t.closed).toBe(true);
    await client.close();
  });

  it("default transport is the centrifuge client", () => {
    const ws = new BitpinWS(new Bitpin({ fetch: new MockFetch().fetch }));
    expect((ws as any).factory("wss://x", null)).toBeInstanceOf(CentrifugeTransport);
  });
});

describe("websocket user identifier", () => {
  it("a failed lookup can be retried", async () => {
    const { client, mock } = setup();
    mock.endpoint("credentials_post_usr_ws_info", { status: 503, body: null });
    const ws = new BitpinWS(client, {
      transport: (url, getToken) => new FakeTransport(url, getToken),
    });
    await expect(ws.watchOrders()).rejects.toBeInstanceOf(errors.ExchangeNotAvailable);
    mock.endpoint("credentials_post_usr_ws_info");
    expect(await (ws as any).userChannel()).toBe("user:order_info#TESTUSR1");
  });
});
