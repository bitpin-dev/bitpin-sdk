// Turn Bitpin responses into ccxt-shaped objects. Pure: no I/O.
import type {
  Balances,
  BankAccount,
  Currency,
  DepositAddress,
  Fee,
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
} from "../types.js";
import { Decimal, toDecimal } from "./numbers.js";
import { toSymbol } from "./symbols.js";

const ZERO = new Decimal(0);
const HUNDRED = new Decimal(100);

export function dec(value: unknown): Decimal | null {
  try {
    return toDecimal(value as string);
  } catch {
    return null;
  }
}

function str(value: unknown): string | null {
  return value === null || value === undefined || value === "" ? null : String(value);
}

/** `2026-10-27T10:15:30.123456+03:30` or `...Z` → Unix milliseconds. */
export function isoToMs(value: unknown): number | null {
  if (typeof value !== "string" || !value) return null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

export function secondsToMs(value: unknown): number | null {
  const number = dec(value);
  return number === null ? null : number.mul(1000).floor().toNumber();
}

export function msToIso(value: number | null): string | null {
  return value === null ? null : new Date(value).toISOString();
}

export function ratioToPercent(value: unknown): Decimal | null {
  const ratio = dec(value);
  return ratio === null ? null : ratio.mul(HUNDRED);
}

const tick = (places: unknown): Decimal => new Decimal(10).pow(-Number(places ?? 0));
const noLimit = () => ({ min: null, max: null });

export function parseMarket(raw: Info): Market {
  const base = String(raw.base);
  const quote = String(raw.quote);
  return {
    id: String(raw.symbol),
    symbol: `${base}/${quote}`,
    base,
    quote,
    baseId: base,
    quoteId: quote,
    active: Boolean(raw.tradable) && !raw.suspended,
    type: "spot",
    spot: true,
    margin: false,
    swap: false,
    future: false,
    option: false,
    contract: false,
    precision: {
      amount: tick(raw.base_amount_precision),
      price: tick(raw.price_precision),
      cost: tick(raw.quote_amount_precision),
    },
    limits: { amount: noLimit(), price: noLimit(), cost: noLimit() },
    info: raw,
  };
}

export function parseCurrency(raw: Info): Currency {
  const code = String(raw.currency);
  return {
    id: code,
    code,
    name: String(raw.name || code),
    active: Boolean(raw.tradable),
    precision: tick(raw.precision),
    info: raw,
  };
}

export function parseTicker(raw: Info): Ticker {
  const timestamp = secondsToMs(raw.timestamp);
  const last = dec(raw.price);
  return {
    symbol: toSymbol(String(raw.symbol)),
    timestamp,
    datetime: msToIso(timestamp),
    high: dec(raw.high),
    low: dec(raw.low),
    bid: null,
    ask: null,
    last,
    close: last,
    open: null,
    change: null,
    percentage: ratioToPercent(raw.daily_change_price),
    average: dec(raw.mean),
    baseVolume: dec(raw.base_volume),
    quoteVolume: dec(raw.quote_volume),
    info: raw,
  };
}

function levels(rows: unknown, descending: boolean): [Decimal, Decimal][] {
  const list = (Array.isArray(rows) ? rows : []).map(
    (r: unknown[]) => [new Decimal(String(r[0])), new Decimal(String(r[1]))] as [Decimal, Decimal],
  );
  return list.sort((a, b) => (descending ? b[0].cmp(a[0]) : a[0].cmp(b[0])));
}

export function parseOrderBook(
  raw: Info,
  symbol: string,
  timestamp: number | null = null,
): OrderBook {
  return {
    symbol,
    bids: levels(raw.bids, true),
    asks: levels(raw.asks, false),
    timestamp,
    datetime: msToIso(timestamp),
    nonce: null,
  };
}

export function parseTrade(raw: Info, symbol: string): Trade {
  const timestamp = secondsToMs(raw.time);
  return {
    id: String(raw.id),
    order: null,
    timestamp,
    datetime: msToIso(timestamp),
    symbol,
    type: null,
    side: String(raw.side),
    takerOrMaker: null,
    price: dec(raw.price),
    amount: dec(raw.base_amount),
    cost: dec(raw.quote_amount),
    fee: null,
    info: raw,
  };
}

export function parseMyTrade(raw: Info): Trade {
  const timestamp = isoToMs(raw.created_at);
  return {
    id: String(raw.id),
    order: str(raw.order_id),
    timestamp,
    datetime: msToIso(timestamp),
    symbol: toSymbol(String(raw.symbol)),
    type: null,
    side: String(raw.side),
    takerOrMaker: null,
    price: dec(raw.price),
    amount: dec(raw.base_amount),
    cost: dec(raw.quote_amount),
    fee: { cost: dec(raw.commission), currency: str(raw.commission_currency) },
    info: raw,
  };
}

export function parseOhlcv(raw: Info): OHLCV {
  return [
    secondsToMs(raw.ts),
    dec(raw.open),
    dec(raw.high),
    dec(raw.low),
    dec(raw.close),
    dec(raw.volume),
  ];
}

function orderStatus(raw: Info): string {
  const state = String(raw.state);
  if (state === "initial" || state === "active") return "open";
  if (state !== "closed") return state;
  const base = dec(raw.base_amount);
  if (base?.gt(0)) return (dec(raw.dealed_base_amount) ?? ZERO).gte(base) ? "closed" : "canceled";
  const quote = dec(raw.quote_amount);
  if (quote?.gt(0))
    return (dec(raw.dealed_quote_amount) ?? ZERO).gte(quote) ? "closed" : "canceled";
  return "closed";
}

const positive = (value: Decimal | null): Decimal | null => (value?.gt(0) ? value : null);

function order(raw: Info, timestamp: number | null, closed: number | null, status: string): Order {
  const amount = dec(raw.base_amount);
  const filled = dec(raw.dealed_base_amount);
  const stop = dec(raw.stop_price);
  const fee: Fee = { cost: dec(raw.commission), currency: null };
  return {
    id: String(raw.id),
    clientOrderId: str(raw.identifier),
    timestamp,
    datetime: msToIso(timestamp),
    lastTradeTimestamp: filled && !filled.isZero() ? closed : null,
    symbol: toSymbol(String(raw.symbol)),
    type: String(raw.type),
    timeInForce: null,
    side: String(raw.side),
    price: positive(dec(raw.price)),
    stopPrice: stop,
    triggerPrice: stop,
    takeProfitPrice: dec(raw.oco_target_price),
    average: positive(dec(raw.average_price)),
    amount,
    cost: dec(raw.dealed_quote_amount),
    filled,
    remaining: amount === null ? null : Decimal.max(amount.sub(filled ?? ZERO), ZERO),
    status,
    fee,
    trades: [],
    reduceOnly: null,
    postOnly: null,
    info: raw,
  };
}

export function parseOrder(raw: Info): Order {
  return order(raw, isoToMs(raw.created_at), isoToMs(raw.closed_at), orderStatus(raw));
}

/** Order-history rows are always closed and use Unix-millisecond times. */
export function parseHistoryOrder(raw: Info): Order {
  const ms = (v: unknown) => (v === null || v === undefined ? null : Number(v));
  return order(
    raw,
    ms(raw.created_at),
    ms(raw.closed_at),
    orderStatus({ ...raw, state: "closed" }),
  );
}

/** Bulk create returns `{orders: [...]}`; older servers return a bare list. */
export function parseBulkOrders(raw: unknown): Order[] {
  const rows = Array.isArray(raw) ? raw : ((raw as Info | null)?.orders ?? []);
  return rows.map(parseOrder);
}

export function parseBalance(rows: Info[]): Balances {
  const result: Balances = { info: rows, free: {}, used: {}, total: {} };
  for (const row of rows) {
    const code = String(row.asset);
    const free = (dec(row.balance) ?? ZERO).add(result.free[code] ?? ZERO);
    const used = (dec(row.frozen) ?? ZERO).add(result.used[code] ?? ZERO);
    result.free[code] = free;
    result.used[code] = used;
    result.total[code] = free.add(used);
    result[code] = { free, used, total: free.add(used) };
  }
  return result;
}

/** Bitpin returns percents (`0.3` = 0.3 %); ccxt uses ratios (`0.003`). */
export function parseTradingFee(raw: Info): TradingFee {
  const maker = dec(raw.maker);
  const taker = dec(raw.taker);
  return {
    symbol: toSymbol(String(raw.symbol)),
    maker: maker === null ? null : maker.div(HUNDRED),
    taker: taker === null ? null : taker.div(HUNDRED),
    percentage: true,
    tierBased: true,
    info: raw,
  };
}

const TX_STATUS: Record<string, string> = { succeed: "ok", failed: "failed", canceled: "canceled" };
const networkCode = (value: unknown): string | null =>
  value && typeof value === "object" ? str((value as Info).code) : str(value);

export function parseDeposit(raw: Info): Transaction {
  const timestamp = isoToMs(raw.created_at);
  return {
    id: String(raw.id),
    txid: str(raw.tx_hash),
    timestamp,
    datetime: msToIso(timestamp),
    network: networkCode(raw.network),
    address: null,
    addressTo: null,
    tag: null,
    type: "deposit",
    amount: dec(raw.amount),
    currency: String(raw.currency),
    status: TX_STATUS[String(raw.state)] ?? "pending",
    updated: null,
    fee: null,
    internal: raw.internal ?? null,
    comment: str(raw.description),
    info: raw,
  };
}

export function parseWithdrawal(raw: Info): Transaction {
  const timestamp = isoToMs(raw.created_at);
  const crypto: Info = raw.crypto_details ?? {};
  const currency = String(raw.currency);
  const address = str(crypto.address);
  return {
    id: String(raw.id),
    txid: str(crypto.tx_hash),
    timestamp,
    datetime: msToIso(timestamp),
    network: str(crypto.network),
    address,
    addressTo: address,
    tag: str(crypto.memo),
    type: "withdrawal",
    amount: dec(raw.amount),
    currency,
    status: TX_STATUS[String(raw.state)] ?? "pending",
    updated: isoToMs(raw.closed_at),
    fee: { cost: dec(raw.commission), currency },
    internal: raw.internal ?? null,
    comment: str(raw.description),
    info: raw,
  };
}

export function parseDepositAddress(raw: Info, network: string | null): DepositAddress {
  return {
    currency: String(raw.currency),
    network,
    address: String(raw.address),
    tag: str(raw.memo),
    info: raw,
  };
}

export function parseNetwork(raw: Info): Network {
  const code = String(raw.code);
  return {
    id: code,
    network: code,
    name: String(raw.title || code),
    deposit: Boolean(raw.can_deposit),
    withdraw: Boolean(raw.can_withdraw),
    addressPattern: str(raw.address_pattern),
    info: raw,
  };
}

/** One row of the currency-networks list. Accepts the v1 and v2 `network` shapes. */
export function parseCurrencyNetwork(raw: Info): Network {
  const network = parseNetwork(raw.network ?? {});
  return {
    ...network,
    deposit: network.deposit && !raw.deposit_under_maintenance,
    withdraw: network.withdraw && !raw.withdraw_under_maintenance,
    info: raw,
  };
}

export function parseBankAccount(raw: Info): BankAccount {
  const currency = raw.currency;
  return {
    id: String(raw.id),
    currency: currency && typeof currency === "object" ? str(currency.currency) : str(currency),
    iban: str(raw.iban),
    card: str(raw.card),
    status: String(raw.state),
    info: raw,
  };
}
