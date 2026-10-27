import { describe, expect, it } from "vitest";
import { HAS } from "../src/generated/spec.js";
import { errors } from "../src/index.js";
import { setup } from "./helpers.js";

const SPECIAL: Record<string, string> = { sandbox: "setSandboxMode" };
const methodName = (feature: string) => SPECIAL[feature] ?? feature;

describe("capability map", () => {
  it.each(Object.keys(HAS))("%s has a method", (feature) => {
    const { client } = setup();
    expect(typeof (client as any)[methodName(feature)]).toBe("function");
  });

  it.each(
    Object.entries(HAS)
      .filter(([, ok]) => !ok)
      .map(([f]) => f),
  )("%s raises NotSupported", async (feature) => {
    const { client } = setup();
    const error = await Promise.resolve()
      .then(() => (client as any)[methodName(feature)]("x"))
      .catch((e) => e);
    expect(error).toBeInstanceOf(errors.NotSupported);
    expect(error.feature).toBe(feature);
  });
});
