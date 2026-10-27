// Turn WebSocket publications into ccxt-shaped objects.
import {
  dec,
  isoToMs,
  msToIso,
  parseMyTrade,
  parseOhlcv,
  parseOrder,
  parseOrderBook,
  parseTrade,
  ratioToPercent,
} from "../core/parse.js";
import { toSymbol } from "../core/symbols.js";
import type { Info, OHLCV, Order, OrderBook, Ticker, Trade } from "../types.js";

/** `currency_price_update`: 24h stats; `change` is a ratio, `time` is in ms. */
export function parseWsTicker(data: Info): Ticker {
  const time = dec(data.time);
  const timestamp = time === null ? null : time.floor().toNumber();
  const last = dec(data.price);
  return {
    symbol: toSymbol(String(data.symbol)),
    timestamp,
    datetime: msToIso(timestamp),
    high: dec(data.max),
    low: dec(data.min),
    bid: null,
    ask: null,
    last,
    close: last,
    open: null,
    change: null,
    percentage: ratioToPercent(data.change),
    average: dec(data.mean),
    baseVolume: dec(data.amount),
    quoteVolume: dec(data.value),
    info: data,
  };
}

/** `candle_update` carries the latest candles of every resolution; keep one. */
export function parseWsOhlcv(data: Info, timeframe: string): OHLCV[] {
  return (data.candles ?? []).filter((c: Info) => c.resolution === timeframe).map(parseOhlcv);
}

export function parseWsOrderBook(data: Info): OrderBook {
  return parseOrderBook(data, toSymbol(String(data.symbol)), isoToMs(data.event_time));
}

export function parseWsTrades(data: Info): Trade[] {
  const symbol = toSymbol(String(data.symbol));
  return (data.matches ?? []).map((row: Info) => parseTrade(row, symbol));
}

export const parseWsOrder = (data: Info): Order => parseOrder(data);
export const parseWsMyTrade = (data: Info): Trade => parseMyTrade(data);
