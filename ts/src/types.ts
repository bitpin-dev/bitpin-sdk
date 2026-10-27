// Result types. Field names follow ccxt's unified structures; numbers are Decimal.
// Every result keeps the raw server response in `info`.
import type { Decimal } from "./core/numbers.js";

export type Info = Record<string, any>;
export interface MinMax {
  min: Decimal | null;
  max: Decimal | null;
}

export interface Market {
  id: string;
  symbol: string;
  base: string;
  quote: string;
  baseId: string;
  quoteId: string;
  active: boolean;
  type: "spot";
  spot: boolean;
  margin: boolean;
  swap: boolean;
  future: boolean;
  option: boolean;
  contract: boolean;
  precision: { amount: Decimal; price: Decimal; cost: Decimal };
  limits: { amount: MinMax; price: MinMax; cost: MinMax };
  info: Info;
}

export interface Currency {
  id: string;
  code: string;
  name: string;
  active: boolean;
  precision: Decimal;
  info: Info;
}

export interface Ticker {
  symbol: string;
  timestamp: number | null;
  datetime: string | null;
  high: Decimal | null;
  low: Decimal | null;
  bid: Decimal | null;
  ask: Decimal | null;
  last: Decimal | null;
  close: Decimal | null;
  open: Decimal | null;
  change: Decimal | null;
  percentage: Decimal | null;
  average: Decimal | null;
  baseVolume: Decimal | null;
  quoteVolume: Decimal | null;
  info: Info;
}

export interface OrderBook {
  symbol: string;
  bids: [Decimal, Decimal][];
  asks: [Decimal, Decimal][];
  timestamp: number | null;
  datetime: string | null;
  nonce: number | null;
}

export interface Fee {
  cost: Decimal | null;
  currency: string | null;
}

export interface Trade {
  id: string;
  order: string | null;
  timestamp: number | null;
  datetime: string | null;
  symbol: string;
  type: string | null;
  side: string;
  takerOrMaker: string | null;
  price: Decimal | null;
  amount: Decimal | null;
  cost: Decimal | null;
  fee: Fee | null;
  info: Info;
}

export interface Order {
  id: string;
  clientOrderId: string | null;
  timestamp: number | null;
  datetime: string | null;
  lastTradeTimestamp: number | null;
  symbol: string;
  type: string;
  timeInForce: string | null;
  side: string;
  price: Decimal | null;
  stopPrice: Decimal | null;
  triggerPrice: Decimal | null;
  takeProfitPrice: Decimal | null;
  average: Decimal | null;
  amount: Decimal | null;
  cost: Decimal | null;
  filled: Decimal | null;
  remaining: Decimal | null;
  status: string;
  fee: Fee;
  trades: Trade[];
  reduceOnly: boolean | null;
  postOnly: boolean | null;
  info: Info;
}

export interface BalanceEntry {
  free: Decimal;
  used: Decimal;
  total: Decimal;
}

/** `{ BTC: {free, used, total}, ..., free: {...}, used: {...}, total: {...}, info: [...] }`, as in ccxt. */
export type Balances = {
  free: Record<string, Decimal>;
  used: Record<string, Decimal>;
  total: Record<string, Decimal>;
  info: Info[];
} & Record<string, any>;

export interface TradingFee {
  symbol: string;
  maker: Decimal | null;
  taker: Decimal | null;
  percentage: boolean;
  tierBased: boolean;
  info: Info;
}

export interface Transaction {
  id: string;
  txid: string | null;
  timestamp: number | null;
  datetime: string | null;
  network: string | null;
  address: string | null;
  addressTo: string | null;
  tag: string | null;
  type: "deposit" | "withdrawal";
  amount: Decimal | null;
  currency: string;
  status: string;
  updated: number | null;
  fee: Fee | null;
  internal: boolean | null;
  comment: string | null;
  info: Info;
}

export interface DepositAddress {
  currency: string;
  network: string | null;
  address: string;
  tag: string | null;
  info: Info;
}

export interface Network {
  id: string;
  network: string;
  name: string;
  deposit: boolean;
  withdraw: boolean;
  addressPattern: string | null;
  info: Info;
}

export interface BankAccount {
  id: string;
  currency: string | null;
  iban: string | null;
  card: string | null;
  status: string;
  info: Info;
}

export interface CancelResult {
  canceled: string[];
  notCanceled: string[];
  info: Info;
}

/** `[timestampMs, open, high, low, close, volume]` */
export type OHLCV = [
  number | null,
  Decimal | null,
  Decimal | null,
  Decimal | null,
  Decimal | null,
  Decimal | null,
];
