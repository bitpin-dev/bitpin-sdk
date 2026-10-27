// Where tokens are cached between client instances and restarts.
// Authenticate allows 3 requests per minute per IP: share tokens across processes with
// FileTokenStore (or your own store, e.g. Redis).
import type { Tokens } from "./core/auth.js";

export interface TokenStore {
  load(keyId: string): Promise<Tokens | null>;
  save(keyId: string, tokens: Tokens): Promise<void>;
  clear(keyId: string): Promise<void>;
}

/** A stable, non-secret id for an API key: a slow PBKDF2 derivation, 16 hex characters. */
export async function keyId(apiKey: string): Promise<string> {
  const { pbkdf2 } = await import("node:crypto");
  const digest = await new Promise<Buffer>((resolve, reject) =>
    pbkdf2(apiKey, "bitpin-sdk/token-store", 100_000, 32, "sha256", (err, key) =>
      err ? reject(err) : resolve(key),
    ),
  );
  return digest.toString("hex").slice(0, 16);
}

/** The default: tokens live as long as the client. */
export class MemoryTokenStore implements TokenStore {
  private readonly tokens = new Map<string, Tokens>();
  async load(keyId: string): Promise<Tokens | null> {
    return this.tokens.get(keyId) ?? null;
  }
  async save(keyId: string, tokens: Tokens): Promise<void> {
    this.tokens.set(keyId, tokens);
  }
  async clear(keyId: string): Promise<void> {
    this.tokens.delete(keyId);
  }
}

const KEY_ID = /^[A-Za-z0-9_-]+$/;

function isTokens(value: unknown): value is Tokens {
  const t = value as Record<string, unknown>;
  return (
    !!t &&
    typeof t.access === "string" &&
    typeof t.refresh === "string" &&
    typeof t.accessExp === "number" &&
    typeof t.refreshExp === "number"
  );
}

/** Tokens in `$XDG_CACHE_HOME/bitpin-sdk/<key id>.json` (default `~/.cache`), mode 0600. Node only. */
export class FileTokenStore implements TokenStore {
  constructor(readonly directory?: string) {}

  private async path(keyId: string): Promise<string> {
    if (!KEY_ID.test(keyId)) throw new Error(`invalid key id '${keyId}'`);
    const { join } = await import("node:path");
    return join(await this.dir(), `${keyId}.json`);
  }

  async dir(): Promise<string> {
    if (this.directory) return this.directory;
    const { homedir } = await import("node:os");
    const { join } = await import("node:path");
    return join(process.env.XDG_CACHE_HOME || join(homedir(), ".cache"), "bitpin-sdk");
  }

  async load(keyId: string): Promise<Tokens | null> {
    const { readFile } = await import("node:fs/promises");
    try {
      const data: unknown = JSON.parse(await readFile(await this.path(keyId), "utf8"));
      return isTokens(data) ? data : null;
    } catch {
      return null;
    }
  }

  async save(keyId: string, tokens: Tokens): Promise<void> {
    const fs = await import("node:fs/promises");
    const { randomBytes } = await import("node:crypto");
    const path = await this.path(keyId);
    const dir = await this.dir();
    await fs.mkdir(dir, { recursive: true, mode: 0o700 });
    await fs.chmod(dir, 0o700).catch(() => undefined);
    // A unique temp file per save: several processes may save at the same time.
    const tmp = `${path}.${process.pid}.${randomBytes(4).toString("hex")}.tmp`;
    try {
      await fs.writeFile(tmp, JSON.stringify(tokens), { mode: 0o600, flag: "wx" });
      await fs.rename(tmp, path);
    } catch (error) {
      await fs.rm(tmp, { force: true });
      throw error;
    }
  }

  async clear(keyId: string): Promise<void> {
    const { rm } = await import("node:fs/promises");
    await rm(await this.path(keyId), { force: true });
  }
}
