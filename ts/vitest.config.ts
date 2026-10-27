import { defineConfig } from "vitest/config";

export default defineConfig({
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
