// Client configuration. Defaults come from spec/bitpin.yaml; every value can be overridden.
import {
  DEFAULT_DOMAIN,
  DOMAINS,
  type Domain,
  type Period,
  RATE_LIMITS,
} from "./generated/spec.js";
import type { TokenStore } from "./tokenStore.js";

const PERIOD_SECONDS: Record<Period, number> = { sec: 1, min: 60, hour: 3600, day: 86400 };

/** At most `limit` requests per `period`. */
export class RateLimit {
  constructor(
    readonly limit: number,
    readonly period: Period,
  ) {
    if (!Number.isInteger(limit) || limit < 1 || !(period in PERIOD_SECONDS)) {
      throw new Error(`invalid rate limit ${limit}/${period}`);
    }
  }

  get periodSeconds(): number {
    return PERIOD_SECONDS[this.period];
  }

  /** Accept a `RateLimit` or a string such as `"10800/min"`. */
  static parse(value: string | RateLimit): RateLimit {
    if (value instanceof RateLimit) return value;
    const match = /^(\d+)\/(sec|min|hour|day)$/.exec(value);
    if (!match || Number(match[1]) < 1) {
      throw new Error(
        `invalid rate limit '${value}'; use '<count>/<sec|min|hour|day>', e.g. '60/min'`,
      );
    }
    return new RateLimit(Number(match[1]), match[2] as Period);
  }
}

export interface BitpinOptions {
  /** API key. */
  apiKey?: string;
  /** Secret key (`secret` also works, as in ccxt). */
  secretKey?: string;
  secret?: string;
  /** API domain: "org" (default), "ir" or "market". REST and WebSocket switch together. */
  domain?: Domain;
  /** Explicit REST base URL; wins over `domain`. */
  restUrl?: string;
  wsUrl?: string;
  /** Milliseconds per request, as in ccxt JS. Default 10 000. */
  timeout?: number;
  /** Retries for idempotent requests only. Default 3. */
  maxRetries?: number;
  enableRateLimit?: boolean;
  /** Per-bucket overrides of the server defaults, e.g. `{ orderbook: "10800/min" }`. */
  rateLimits?: Record<string, string | RateLimit>;
  userAgent?: string;
  tokenStore?: TokenStore;
  /** Injected for tests and custom transports. */
  fetch?: typeof fetch;
  /** Seconds since the epoch. */
  clock?: () => number;
  sleep?: (seconds: number) => Promise<void>;
  /** Factory for the WebSocket transport (tests). */
  wsTransport?: unknown;
}

export interface ResolvedConfig {
  readonly apiKey: string | null;
  readonly secretKey: string | null;
  readonly domain: Domain;
  readonly restUrl: string;
  readonly wsUrl: string;
  readonly timeout: number;
  readonly maxRetries: number;
  readonly enableRateLimit: boolean;
  readonly userAgent: string | null;
  readonly hasCredentials: boolean;
  rateLimit(bucket: string): RateLimit;
  allRateLimits(): Record<string, RateLimit>;
}

/** Merge options, `BITPIN_API_KEY`/`BITPIN_SECRET_KEY` from `env`, and the spec defaults. */
export function resolveConfig(
  options: BitpinOptions,
  env: Record<string, string | undefined> = {},
): ResolvedConfig {
  const overrides: Record<string, RateLimit> = {};
  for (const [name, value] of Object.entries(options.rateLimits ?? {})) {
    if (!(name in RATE_LIMITS)) {
      throw new Error(
        `unknown rate-limit bucket '${name}'; known buckets: ${Object.keys(RATE_LIMITS).sort().join(", ")}`,
      );
    }
    overrides[name] = RateLimit.parse(value);
  }
  const domain = (options.domain ?? env.BITPIN_DOMAIN ?? DEFAULT_DOMAIN) as Domain;
  if (!(domain in DOMAINS)) {
    throw new Error(
      `unknown domain '${domain}'; use one of: ${Object.keys(DOMAINS).sort().join(", ")}`,
    );
  }
  const maxRetries = options.maxRetries ?? 3;
  if (maxRetries < 0) throw new Error("maxRetries must be >= 0");
  const apiKey = options.apiKey ?? env.BITPIN_API_KEY ?? null;
  const secretKey = options.secretKey ?? options.secret ?? env.BITPIN_SECRET_KEY ?? null;

  const rateLimit = (bucket: string): RateLimit => {
    const override = overrides[bucket];
    if (override) return override;
    const [limit, period] = RATE_LIMITS[bucket]!;
    return new RateLimit(limit, period);
  };
  const config: ResolvedConfig = {
    apiKey,
    secretKey,
    domain,
    restUrl: options.restUrl ?? DOMAINS[domain].rest,
    wsUrl: options.wsUrl ?? DOMAINS[domain].ws,
    timeout: options.timeout ?? 10_000,
    maxRetries,
    enableRateLimit: options.enableRateLimit ?? true,
    userAgent: options.userAgent ?? null,
    hasCredentials: Boolean(apiKey && secretKey),
    rateLimit,
    allRateLimits: () =>
      Object.fromEntries(Object.keys(RATE_LIMITS).map((name) => [name, rateLimit(name)])),
  };
  const shown = () => ({
    ...config,
    apiKey: apiKey ? "***" : null,
    secretKey: secretKey ? "***" : null,
  });
  Object.defineProperties(config, {
    apiKey: { value: apiKey, enumerable: false },
    secretKey: { value: secretKey, enumerable: false },
    toJSON: { value: shown, enumerable: false },
    toString: { value: () => `Config(${JSON.stringify(shown())})`, enumerable: false },
    [Symbol.for("nodejs.util.inspect.custom")]: {
      value: () => `Config(${JSON.stringify(shown())})`,
      enumerable: false,
    },
  });
  return Object.freeze(config);
}
