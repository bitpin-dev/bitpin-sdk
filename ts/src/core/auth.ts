// Access/refresh token lifecycle. Pure: decides what to do, the client does the network call.
// Authenticate allows 3 requests per minute per IP, so tokens are cached and refreshed early.
import { CONSTANTS } from "../generated/spec.js";

export type Action = "ok" | "refresh" | "authenticate";

export interface Tokens {
  access: string;
  refresh: string;
  accessExp: number;
  refreshExp: number;
}

/** The `exp` claim of a JWT, read without verifying the signature; null if unreadable. */
export function jwtExp(token: string): number | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const claims: unknown = JSON.parse(Buffer.from(parts[1]!, "base64url").toString("utf8"));
    if (claims && typeof claims === "object" && !Array.isArray(claims)) {
      const exp = (claims as { exp?: unknown }).exp;
      if (typeof exp === "number" && Number.isFinite(exp)) return exp;
    }
  } catch {
    // not JSON
  }
  return null;
}

export class TokenState {
  tokens: Tokens | null = null;

  constructor(private readonly clock: () => number) {}

  get accessToken(): string | null {
    return this.tokens?.access ?? null;
  }

  action(): Action {
    if (!this.tokens) return "authenticate";
    const now = this.clock();
    if (now >= this.tokens.refreshExp) return "authenticate";
    if (now >= this.tokens.accessExp - CONSTANTS.token_refresh_margin_seconds) return "refresh";
    return "ok";
  }

  private exp(token: string, ttl: number): number {
    return jwtExp(token) ?? this.clock() + ttl;
  }

  /** Store the `{access, refresh}` pair returned by authenticate. */
  setTokens(data: { access: unknown; refresh: unknown }): Tokens {
    const access = String(data.access);
    const refresh = String(data.refresh);
    this.tokens = {
      access,
      refresh,
      accessExp: this.exp(access, CONSTANTS.access_token_ttl_seconds),
      refreshExp: this.exp(refresh, CONSTANTS.refresh_token_ttl_seconds),
    };
    return this.tokens;
  }

  /** Store the `{access}` returned by refresh; the refresh token is not rotated. */
  setAccess(data: { access: unknown }): Tokens {
    if (!this.tokens) throw new Error("setAccess() called before setTokens()");
    const access = String(data.access);
    this.tokens = {
      ...this.tokens,
      access,
      accessExp: this.exp(access, CONSTANTS.access_token_ttl_seconds),
    };
    return this.tokens;
  }

  /** After a 401: refresh next time, but only if `token` is still the current one. */
  expireAccess(token?: string): void {
    if (token !== undefined && this.accessToken !== token) return;
    if (this.tokens) this.tokens = { ...this.tokens, accessExp: 0 };
  }

  load(tokens: Tokens): void {
    this.tokens = tokens;
  }

  clear(): void {
    this.tokens = null;
  }
}
