# TypeScript and Go SDKs — design addendum

Status: owner asked for TypeScript first, then Go · 2026-10-27 · extends `2026-10-27-bitpin-sdk-design.md`

Everything in the main design holds: one spec (`spec/bitpin.yaml`), one set of fixtures, ccxt names and result structures, exact decimals, server-default rate-limit buckets overridable per bucket, token caching, retries only for idempotent requests, `NotSupported` (en + fa) for what Bitpin lacks, `/api/` endpoints only, no live calls in CI. This addendum records only what differs per language.

## Shared

- Each language generates its endpoint table from the spec (`scripts/gen_ts.py`, `scripts/gen_go.py`) with a `--check` mode in CI.
- Each language's tests replay `fixtures/` and assert the exact request sent.
- Each is a release-please component: tags `ts-v0.1.0` and `go/v0.1.0` (the `go/` prefix is what Go modules in a subdirectory require), its own `CHANGELOG.md`.
- Docs: one page per language (`docs/{en,fa}/typescript.md`, `docs/{en,fa}/go.md`) mapping the shared concepts to that language's names, plus a section in `llms.txt`. The concept pages (rate limits, errors, not-supported, …) stay shared and use Python in examples.

## TypeScript (`ts/`, npm `bitpin-sdk`)

- **Runtime:** Node ≥ 22 (current LTS lines), also Bun and Deno; uses the global `fetch`. Browsers are not a target: API secrets don't belong in a browser.
- **Package:** ESM and CommonJS builds with type declarations (tsup), `"sideEffects": false`. TypeScript strict.
- **API:** one async class `Bitpin` (JavaScript is async; there is no separate sync client). ccxt JS names: `fetchTicker`, `createOrder`, `watchOrderBook`, implicit methods in camelCase (`publicGetMktTickers`). Constructor takes ccxt keys (`apiKey`, `secret`) or SDK keys (`apiKey`, `secretKey`), `timeout` in milliseconds as in ccxt JS.
- **Numbers:** `Decimal` from `decimal.js` (re-exported), the only runtime dependency besides `centrifuge` for WebSocket. Inputs accept `Decimal | string | number`.
- **Token store:** async `TokenStore` interface; `MemoryTokenStore` default; `FileTokenStore` (Node only, `fs` imported lazily) with mode 0600 and a PBKDF2 key id.
- **WebSocket:** `centrifuge` (official client), same per-watch queues as Python.
- **Tooling:** vitest (coverage ≥ 95 % branches), biome (lint + format), `tsc --noEmit`, npm with a committed lockfile.
- **Publishing:** npm trusted publishing (OIDC) with provenance from the release workflow; no npm token stored. The owner registers the publisher on npmjs.com once.

## Go (`go/`, module `github.com/bitpin-dev/bitpin-sdk/go`)

- **Go ≥ 1.24.** Package `bitpin`.
- **API:** `bitpin.New(bitpin.Config{...})` returns `*Client`. Every call takes a `context.Context` first and returns `(T, error)`, the Go way; names are ccxt's in Go case: `FetchTicker`, `CreateOrder`, `WatchOrderBook`. Optional ccxt arguments become option structs (`FetchOrdersOptions{Symbol, Since, Limit, Params}`).
- **Results:** typed structs with ccxt field names (`Order.ClientOrderID`, `Order.Filled`, …) and the raw response in `Info map[string]any`.
- **Numbers:** `github.com/shopspring/decimal`.
- **Errors:** an `*Error` carrying `Kind` (the ccxt class, e.g. `ErrInsufficientFunds`), status, body and endpoint id; `errors.Is(err, bitpin.ErrInvalidOrder)` works up the ccxt hierarchy.
- **Concurrency:** the client is safe for concurrent use; single-flight token refresh with a mutex; rate-limit reservations as in Python.
- **WebSocket:** `github.com/centrifugal/centrifuge-go`; `Watch*` methods block until the next update or the context ends.
- **Tooling:** `go test -race -cover` (≥ 90 % statements, Go's coverage has no branch mode), `go vet`, `staticcheck`, `gofmt`.
- **Publishing:** nothing to upload; the `go/v0.1.0` tag is the release, and pkg.go.dev picks it up.
