/**
 * Errors thrown by the SDK. The hierarchy follows ccxt so existing handlers keep working.
 *
 * BitpinError
 * ├── ExchangeError                 the server answered with an error
 * │   ├── AuthenticationError       bad key/secret, IP not allowed, token revoked
 * │   ├── PermissionDenied          account not allowed (e.g. KYC level)
 * │   ├── InsufficientFunds
 * │   ├── InvalidOrder              rejected order or cancel
 * │   ├── OrderNotFound
 * │   ├── BadRequest                invalid parameters
 * │   │   ├── BadSymbol
 * │   │   └── InvalidOTP            see `code`
 * │   └── NotSupported              Bitpin doesn't offer this yet (see `feature`)
 * └── NetworkError                  the request may not have reached the server
 *     ├── RateLimitExceeded         see `retryAfter`
 *     ├── RequestTimeout
 *     └── ExchangeNotAvailable      5xx / maintenance
 */

export interface ErrorDetails {
  status?: number | null;
  body?: unknown;
  endpointId?: string | null;
  cause?: unknown;
}

export class BitpinError extends Error {
  readonly status: number | null;
  readonly body: unknown;
  readonly endpointId: string | null;

  constructor(message: string, details: ErrorDetails = {}) {
    super(message, details.cause === undefined ? undefined : { cause: details.cause });
    this.name = new.target.name;
    this.status = details.status ?? null;
    this.body = details.body ?? null;
    this.endpointId = details.endpointId ?? null;
  }
}

export class ExchangeError extends BitpinError {}
export class AuthenticationError extends ExchangeError {}
export class PermissionDenied extends ExchangeError {}
export class InsufficientFunds extends ExchangeError {}
export class InvalidOrder extends ExchangeError {}
export class OrderNotFound extends ExchangeError {}
export class BadRequest extends ExchangeError {}
export class BadSymbol extends BadRequest {}

/** The withdrawal OTP was rejected: `invalid_otp`, `otp1_already_verified` or `extra_try`. */
export class InvalidOTP extends BadRequest {
  readonly code: string | null;
  constructor(message: string, details: ErrorDetails & { code?: string | null } = {}) {
    super(message, details);
    this.code = details.code ?? null;
  }
}

/** Bitpin doesn't offer this yet. `feature` is the ccxt capability name. */
export class NotSupported extends ExchangeError {
  readonly feature: string;
  constructor(message: string, details: ErrorDetails & { feature?: string } = {}) {
    super(message, details);
    this.feature = details.feature ?? "";
  }
}

export class NetworkError extends BitpinError {}

/** HTTP 429. `retryAfter` is the server's hint in seconds, when it gives one. */
export class RateLimitExceeded extends NetworkError {
  readonly retryAfter: number | null;
  constructor(message: string, details: ErrorDetails & { retryAfter?: number | null } = {}) {
    super(message, details);
    this.retryAfter = details.retryAfter ?? null;
  }
}

export class RequestTimeout extends NetworkError {}
export class ExchangeNotAvailable extends NetworkError {}
