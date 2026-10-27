---
name: sync-with-core
description: Re-verify spec/bitpin.yaml (rate limits, constants, request fields, response shapes, error codes) against the Bitpin server's own source code. Use when a maintainer with access to Bitpin's private backend asks to check the SDK is still accurate, or before a release.
---

# Sync the spec with Bitpin's server

Only maintainers with read access to Bitpin's private backend can run this. The backend's code, paths and internal names stay out of this public repository: findings land here only as spec values, fixtures and tests.

1. **Ask** the user for the local path of the backend checkout. Without one, stop: the public docs alone are not authoritative (their English and Persian versions disagree).
2. **Routes.** List the backend's routes under `/api/`. Every one that a trader would use is in `spec/bitpin.yaml`, or is consciously excluded (test-only, internal or deprecated); the deprecated v1 wallet routes stay out. Record new and removed routes.
3. **Rate limits.** For every endpoint, find its throttle classes and their default rate. Compare with `rate_limits` and `buckets`, including throttles a request consumes from another bucket. Per-user VIP tiers are ignored: users configure them.
4. **Shapes.** For every endpoint, compare the serializer's request fields (names, required, types) and response fields with the fixture and the parser.
5. **Errors.** Compare status codes and `detail`/`code` strings with the `errors` rules.
6. **Constants.** Token lifetimes, page-size maxima, bulk sizes, candle limits, history ranges.
7. **Report** every difference to the user as a table: what, spec value, server value. Done when every endpoint in the spec has been checked in steps 3–5.
8. **Fix** each confirmed difference with the `add-endpoint` skill. Commit as `fix(spec): …`, describing the behaviour, never the backend's files.
