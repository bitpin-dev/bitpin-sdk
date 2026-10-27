# Rule: Go

- Module `github.com/bitpin-dev/bitpin-sdk/go`, Go ≥ 1.26 (`go` directive), `toolchain` pinned to the newest Go. Keep dependencies on their newest releases. From Iran use `GOPROXY=https://goproxy.cn,direct` (proxy.golang.org downloads return 403); `GOTOOLCHAIN=local` is the last resort.
- Every exported call takes `context.Context` first and returns `(T, error)`. The Client is safe for concurrent use: state behind mutexes, single-flight auth, limiter reservations under its own lock. Run tests with `-race`.
- Errors are `*Error` with a `Kind` from the `Err*` sentinels; `errors.Is` walks the ccxt hierarchy. Credentials requests never wrap the transport error (it holds the request body).
- Numbers are shopspring `decimal.Decimal`; nullable result fields are `*Decimal`; JSON numbers are decoded with `UseNumber` and kept as strings, so no float rounding.
- Behaviour matches Python and TypeScript; change all three together. Tests replay `fixtures/` through `mockHTTP` and `fakeTime` in `helpers_test.go` and assert the exact request sent.
- Releases are `go/vX.Y.Z` tags from release-please; there is nothing to upload.
