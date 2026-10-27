/**
 * Official TypeScript SDK for the Bitpin exchange.
 *
 *     import { Bitpin } from "@bitpin-dev/bitpin-sdk";
 *
 * Docs: https://bitpin-dev.github.io/bitpin-sdk/typescript/
 */
export { Bitpin, type OrderRequest, type Params, TIMEFRAMES } from "./client.js";
export { type BitpinOptions, RateLimit, type ResolvedConfig } from "./config.js";
export type { Tokens } from "./core/auth.js";
export { Decimal, type Numeric } from "./core/numbers.js";
export * as errors from "./errors.js";
export * from "./errors.js";
export type { Domain } from "./generated/spec.js";
export { FileTokenStore, keyId, MemoryTokenStore, type TokenStore } from "./tokenStore.js";
export type * from "./types.js";
export { VERSION } from "./version.js";
export { BitpinWS, type TransportFactory } from "./ws/client.js";
export type { GetToken, Transport } from "./ws/transport.js";
