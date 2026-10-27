import { defineConfig } from "tsup";

// Declarations come from `tsc -p tsconfig.build.json` (TypeScript 7 has no JS API for tsup's dts).
export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm", "cjs"],
  dts: false,
  sourcemap: true,
  clean: true,
  target: "node22",
});
