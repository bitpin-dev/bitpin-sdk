// Helpers shared by the examples. Credentials come from BITPIN_API_KEY / BITPIN_SECRET_KEY.
// Examples that place orders only print what they would send, unless you pass --live.
import { parseArgs } from "node:util";

export type Options = Record<string, { type: "string" | "boolean"; default?: string | boolean }>;

export function args(argv: string[], options: Options): Record<string, string | boolean | undefined> {
  return parseArgs({ args: argv, options: { live: { type: "boolean", default: false }, ...options }, strict: true }).values;
}

export function show(title: string, value: unknown): void {
  console.log(`== ${title}`);
  console.log(JSON.stringify(value, (_k, v) => (v && typeof v === "object" && v.constructor?.name === "Decimal" ? String(v) : v), 2));
}

export function dryRun(action: string, value: unknown): void {
  show(`DRY-RUN ${action} (pass --live to send)`, value);
}
