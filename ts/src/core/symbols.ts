// Convert between ccxt symbols (`BTC/IRT`) and Bitpin market ids (`BTC_IRT`).
import { BadSymbol } from "../errors.js";

const PART = /^[A-Z0-9]+$/;

function split(value: string, sep: string): [string, string] | null {
  const parts = value.split(sep);
  if (parts.length !== 2 || !parts.every((p) => PART.test(p))) return null;
  return [parts[0]!, parts[1]!];
}

/** `"btc/irt"`, `"BTC/IRT"` or `"BTC_IRT"` → `"BTC_IRT"`. */
export function toMarketId(symbol: string): string {
  const value = symbol.trim().toUpperCase();
  for (const sep of ["/", "_"]) {
    if (value.includes(sep)) {
      const parts = split(value, sep);
      if (parts) return `${parts[0]}_${parts[1]}`;
    }
  }
  throw new BadSymbol(`invalid symbol '${symbol}'; use 'BASE/QUOTE', e.g. 'BTC/IRT'`);
}

/** `"BTC_IRT"` → `"BTC/IRT"`. */
export function toSymbol(marketId: string): string {
  const parts = split(marketId, "_");
  if (!parts) throw new BadSymbol(`invalid market id '${marketId}'`);
  return `${parts[0]}/${parts[1]}`;
}
