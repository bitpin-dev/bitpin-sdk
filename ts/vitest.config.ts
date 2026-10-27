import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "bitpin-sdk": fileURLToPath(new URL("./src/index.ts", import.meta.url)) } },
  test: {
    include: ["test/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      exclude: ["src/generated/**", "src/ws/transport.ts"],
      thresholds: { branches: 95, lines: 95, functions: 95, statements: 95 },
    },
  },
});
