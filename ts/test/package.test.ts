import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

describe("package.json", () => {
  it("is published under the bitpin-dev scope", () => {
    expect(pkg.name).toBe("@bitpin-dev/bitpin-sdk");
    expect(pkg.publishConfig).toEqual({ access: "public" });
  });

  it("exports itself, so tools can read the installed version", () => {
    expect(pkg.exports["./package.json"]).toBe("./package.json");
  });
});
