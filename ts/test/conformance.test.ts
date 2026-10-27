// Every SDK must parse the shared fixtures into the same result as the Python reference
// (fixtures/expected.json, written by scripts/gen_expected.py).
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { Decimal } from "../src/core/numbers.js";
import * as parse from "../src/core/parse.js";
import { body } from "./helpers.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const expected: Record<
  string,
  { parser: string; fixture: string; path: (string | number)[]; args: unknown[]; output: unknown }
> = JSON.parse(readFileSync(join(ROOT, "fixtures", "expected.json"), "utf8"));

const PARSERS: Record<string, (...args: any[]) => unknown> = {
  parse_market: parse.parseMarket,
  parse_currency: parse.parseCurrency,
  parse_ticker: parse.parseTicker,
  parse_order_book: parse.parseOrderBook,
  parse_trade: parse.parseTrade,
  parse_my_trade: parse.parseMyTrade,
  parse_ohlcv: parse.parseOhlcv,
  parse_order: parse.parseOrder,
  parse_history_order: parse.parseHistoryOrder,
  parse_bulk_orders: parse.parseBulkOrders,
  parse_balance: parse.parseBalance,
  parse_trading_fee: parse.parseTradingFee,
  parse_deposit: parse.parseDeposit,
  parse_withdrawal: parse.parseWithdrawal,
  parse_deposit_address: parse.parseDepositAddress,
  parse_currency_network: parse.parseCurrencyNetwork,
  parse_network: parse.parseNetwork,
  parse_bank_account: parse.parseBankAccount,
};

const key = (k: string) => k.toLowerCase().replaceAll("_", "");

function normalize(value: unknown): unknown {
  if (Decimal.isDecimal(value)) return (value as Decimal).toFixed();
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([k]) => k !== "info")
        .map(([k, v]) => [k, normalize(v)]),
    );
  }
  return value;
}

const isEmpty = (v: unknown) =>
  v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);

/** Compare by the expected keys; null in the reference matches null, undefined, "" or absent. */
function compare(want: unknown, got: unknown, path: string, problems: string[]): void {
  if (isEmpty(want)) {
    if (!isEmpty(got)) problems.push(`${path}: expected empty, got ${JSON.stringify(got)}`);
    return;
  }
  if (Array.isArray(want)) {
    if (!Array.isArray(got) || got.length !== want.length) {
      problems.push(`${path}: expected ${want.length} items, got ${JSON.stringify(got)}`);
      return;
    }
    for (const [i, w] of want.entries()) compare(w, got[i], `${path}[${i}]`, problems);
    return;
  }
  if (typeof want === "object") {
    const actual = Object.fromEntries(
      Object.entries((got ?? {}) as object).map(([k, v]) => [key(k), v]),
    );
    for (const [k, w] of Object.entries(want as object))
      compare(w, actual[key(k)], `${path}.${k}`, problems);
    return;
  }
  if (String(want) !== String(got))
    problems.push(`${path}: expected ${JSON.stringify(want)}, got ${JSON.stringify(got)}`);
}

describe("conformance with the Python reference", () => {
  it.each(Object.entries(expected))("%s", (_name, c) => {
    let row: any = body(c.fixture);
    for (const step of c.path) row = row[step];
    const problems: string[] = [];
    compare(c.output, normalize(PARSERS[c.parser]!(row, ...c.args)), "$", problems);
    expect(problems).toEqual([]);
  });

  it("covers every parser", () => {
    expect(new Set(Object.values(expected).map((c) => c.parser))).toEqual(
      new Set(Object.keys(PARSERS)),
    );
  });
});
