// Map an HTTP error response to an SDK error, using the rules in the spec.
import * as errors from "../errors.js";
import { ERROR_RULES, NOT_SUPPORTED } from "../generated/spec.js";

const RETRY_AFTER = /available in (\d+(?:\.\d+)?) second/i;
const OTP_CODES = ["invalid_otp", "otp1_already_verified", "extra_try"];

const CLASSES: Record<
  string,
  new (
    message: string,
    details: errors.ErrorDetails,
  ) => errors.BitpinError
> = {
  ExchangeError: errors.ExchangeError,
  AuthenticationError: errors.AuthenticationError,
  PermissionDenied: errors.PermissionDenied,
  InsufficientFunds: errors.InsufficientFunds,
  InvalidOrder: errors.InvalidOrder,
  OrderNotFound: errors.OrderNotFound,
  BadRequest: errors.BadRequest,
  ExchangeNotAvailable: errors.ExchangeNotAvailable,
};

function bodyText(body: unknown): string {
  if (body === null || body === undefined) return "";
  return typeof body === "string" ? body : JSON.stringify(body);
}

function detail(body: unknown): string {
  if (body && typeof body === "object" && !Array.isArray(body)) {
    for (const key of ["detail", "code", "message"]) {
      const value = (body as Record<string, unknown>)[key];
      if (typeof value === "string") return value;
    }
  }
  return bodyText(body).slice(0, 200);
}

function retryAfter(body: unknown, header: string | null | undefined): number | null {
  if (header !== null && header !== undefined) {
    const seconds = Number(header);
    if (header.trim() !== "" && Number.isFinite(seconds)) return seconds;
  }
  const match = RETRY_AFTER.exec(bodyText(body));
  return match ? Number(match[1]) : null;
}

/** The error for an error response. The caller throws it. */
export function mapError(
  endpointId: string,
  status: number,
  body: unknown,
  retryAfterHeader?: string | null,
): errors.BitpinError {
  const text = bodyText(body).toLowerCase();
  let name = "ExchangeError";
  for (const rule of ERROR_RULES) {
    if (rule.status !== status) continue;
    if (rule.paths.length && !rule.paths.some((p) => endpointId.startsWith(p))) continue;
    if (rule.detail.length && !rule.detail.some((d) => text.includes(d.toLowerCase()))) continue;
    name = rule.error;
    break;
  }
  const reason = detail(body);
  const message = reason ? `${status} ${endpointId}: ${reason}` : `${status} ${endpointId}`;
  const details = { status, body, endpointId };
  if (name === "RateLimitExceeded") {
    return new errors.RateLimitExceeded(message, {
      ...details,
      retryAfter: retryAfter(body, retryAfterHeader),
    });
  }
  if (name === "InvalidOTP") {
    return new errors.InvalidOTP(message, {
      ...details,
      code: OTP_CODES.find((c) => text.includes(c)) ?? null,
    });
  }
  return new CLASSES[name]!(message, details);
}

/** The NotSupported error for a ccxt capability Bitpin doesn't offer, in English and Persian. */
export function notSupported(feature: string): errors.NotSupported {
  const [en, fa] = NOT_SUPPORTED[feature]!;
  return new errors.NotSupported(`${en}\n${fa}`, { feature });
}
