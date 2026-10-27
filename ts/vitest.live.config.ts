import { defineConfig } from "vitest/config";

// Live, read-only suite: npm run test:live (needs BITPIN_LIVE=1). Never part of `npm test`.
export default defineConfig({ test: { include: ["test/live/**/*.live.ts"], testTimeout: 30_000 } });
