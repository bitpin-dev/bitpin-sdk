// Exact decimals. Amounts and prices never pass through float arithmetic.
import Decimal from "decimal.js";

export { Decimal };
export type Numeric = Decimal | string | number;

/** Parse a server or user value; `null` for null, undefined or "". */
export function toDecimal(value: Numeric | null | undefined): Decimal | null {
  if (value === null || value === undefined || value === "") return null;
  if (
    typeof value === "boolean" ||
    (typeof value !== "string" && typeof value !== "number" && !Decimal.isDecimal(value))
  ) {
    throw new Error(`not a number: ${String(value)}`);
  }
  try {
    return new Decimal(value);
  } catch {
    throw new Error(`not a number: ${String(value)}`);
  }
}

/** Plain decimal string for the API: no exponent, no trailing zeros (`1E-8` → `0.00000001`). */
export function fmtDecimal(value: Numeric): string {
  const number = toDecimal(value);
  if (number === null || !number.isFinite())
    throw new Error(`not a finite number: ${String(value)}`);
  return number.toFixed(); // decimal.js prints -0 as "0"
}
