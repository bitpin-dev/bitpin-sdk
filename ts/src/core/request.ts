// Build HTTP requests from the endpoint table. Pure: no I/O.
import type { ResolvedConfig } from "../config.js";
import { type Auth, ENDPOINTS, type Method } from "../generated/spec.js";
import { Decimal, fmtDecimal } from "./numbers.js";

export interface BuiltRequest {
  readonly endpointId: string;
  readonly method: Method;
  readonly url: string;
  readonly params: Record<string, string> | undefined;
  readonly body: unknown;
  readonly auth: Auth;
  readonly buckets: readonly string[];
  readonly idempotent: boolean;
}

function queryValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Decimal.isDecimal(value) || typeof value === "number") return fmtDecimal(value as Decimal);
  if (Array.isArray(value)) return value.map(queryValue).join(",");
  return String(value);
}

function bodyValue(value: unknown): unknown {
  if (typeof value === "boolean" || value === null) return value;
  if (Decimal.isDecimal(value) || typeof value === "number") return fmtDecimal(value as Decimal);
  if (Array.isArray(value)) return value.map(bodyValue);
  if (typeof value === "object" && value !== undefined) {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => [k, bodyValue(v)]),
    );
  }
  return value;
}

export function buildRequest(
  config: ResolvedConfig,
  endpointId: string,
  pathParams: Record<string, unknown> = {},
  params?: Record<string, unknown>,
  body?: unknown,
): BuiltRequest {
  const endpoint = ENDPOINTS[endpointId];
  if (!endpoint) throw new Error(`unknown endpoint ${endpointId}`);
  let path = endpoint.path;
  for (const [key, value] of Object.entries(pathParams)) {
    path = path.replace(`{${key}}`, encodeURIComponent(String(value)));
  }
  const missing = /\{(\w+)\}/.exec(path);
  if (missing) throw new Error(`missing path parameter '${missing[1]}' for ${endpointId}`);

  const query: Record<string, string> = {};
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null) query[key] = queryValue(value);
  }
  return {
    endpointId,
    method: endpoint.method,
    url: config.restUrl.replace(/\/+$/, "") + path,
    params: Object.keys(query).length ? query : undefined,
    body: body === undefined ? undefined : bodyValue(body),
    auth: endpoint.auth,
    buckets: endpoint.buckets,
    idempotent: endpoint.idempotent,
  };
}
