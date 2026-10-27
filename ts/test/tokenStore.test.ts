import { pbkdf2Sync } from "node:crypto";
import { mkdir, mkdtemp, readdir, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { FileTokenStore, keyId, MemoryTokenStore } from "../src/tokenStore.js";

const TOKENS = { access: "a", refresh: "r", accessExp: 100, refreshExp: 200 };
const temp = () => mkdtemp(join(tmpdir(), "bitpin-"));

describe("token stores", () => {
  it("key id is a slow PBKDF2 hash, not the key", async () => {
    const id = await keyId("MY-API-KEY");
    expect(id).toBe(
      pbkdf2Sync("MY-API-KEY", "bitpin-sdk/token-store", 100_000, 32, "sha256")
        .toString("hex")
        .slice(0, 16),
    );
    expect(id).not.toContain("MY-API-KEY");
  });

  it("memory store", async () => {
    const store = new MemoryTokenStore();
    expect(await store.load("k")).toBeNull();
    await store.save("k", TOKENS);
    expect(await store.load("k")).toEqual(TOKENS);
    await store.clear("k");
    expect(await store.load("k")).toBeNull();
  });

  it("file store round trip, private permissions, no temp leftovers", async () => {
    const dir = join(await temp(), "cache");
    const store = new FileTokenStore(dir);
    await store.save("abc", TOKENS);
    expect(await new FileTokenStore(dir).load("abc")).toEqual(TOKENS);
    if (process.platform !== "win32") {
      expect((await stat(join(dir, "abc.json"))).mode & 0o777).toBe(0o600);
      expect((await stat(dir)).mode & 0o777).toBe(0o700);
    }
    expect(await readdir(dir)).toEqual(["abc.json"]);
    await store.clear("abc");
    await store.clear("abc");
    expect(await store.load("abc")).toBeNull();
  });

  it("ignores corrupt or wrongly typed files and rejects path tricks", async () => {
    const dir = await temp();
    const store = new FileTokenStore(dir);
    await writeFile(join(dir, "abc.json"), "{not json");
    expect(await store.load("abc")).toBeNull();
    await writeFile(join(dir, "abc.json"), JSON.stringify({ ...TOKENS, accessExp: "soon" }));
    expect(await store.load("abc")).toBeNull();
    await expect(store.save("../x", TOKENS)).rejects.toThrow(/key id/);
  });

  it("surfaces write failures and cleans up", async () => {
    const dir = await temp();
    await mkdir(join(dir, "abc.json"));
    await expect(new FileTokenStore(dir).save("abc", TOKENS)).rejects.toThrow();
    expect((await readdir(dir)).filter((f) => f.endsWith(".tmp"))).toEqual([]);
  });

  it("defaults to XDG_CACHE_HOME", async () => {
    const previous = process.env.XDG_CACHE_HOME;
    process.env.XDG_CACHE_HOME = "/tmp/xdg";
    expect(await new FileTokenStore().dir()).toBe("/tmp/xdg/bitpin-sdk");
    delete process.env.XDG_CACHE_HOME;
    expect(await new FileTokenStore().dir()).toMatch(/\.cache\/bitpin-sdk$/);
    if (previous !== undefined) process.env.XDG_CACHE_HOME = previous;
  });
});
