# Rule: TypeScript

- Node ≥ 22, TypeScript strict (`noUncheckedIndexedAccess`), ESM sources with `.js` import suffixes. Keep dependencies on the newest releases; adapt the build rather than downgrading.
- Runtime dependencies stay minimal: `decimal.js` and `centrifuge`. Node built-ins (`fs`, `crypto`) are imported lazily, so the package loads in Bun and Deno.
- The behaviour matches the Python SDK: same spec tables (`src/generated/spec.ts`), same fixtures, same validation messages where practical. When you change behaviour in one language, change it in the other in the same PR.
- Prices and amounts are `Decimal`; requests carry `fmtDecimal` strings. Accept `Decimal | string | number` as input.
- ccxt JS names: camelCase methods, `timeout` in milliseconds, implicit methods `publicGetMktTickers`.
- Tests: vitest with `MockFetch` and `FakeTime` from `test/helpers.ts`. Assert the exact request sent; every write method has a sent-once test; coverage gate 95 % branches.
- `biome check` and `tsc --noEmit` are clean before committing. Mind Biome's `--unsafe` fixes: `a && a.b()` → `a?.b()` turns `null` into `undefined`.
