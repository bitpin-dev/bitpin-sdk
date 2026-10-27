---
name: add-endpoint
description: Add or change a Bitpin API endpoint, response field, error or capability across spec, fixtures, generated code, the Python client, tests and both languages' docs. Use when the API gains an endpoint, a field changes shape, or a "not available yet" feature becomes available.
---

# Add or change an endpoint

The spec is the contract; work outward from it. Each step ends when its check passes.

1. **Confirm it's public.** The path starts with `/api/`. Anything else is out of scope; tell the user and stop.
2. **Spec.** Add or edit the entry in `spec/bitpin.yaml`: id, method, path (trailing slash), auth, buckets, idempotent, docs. Add a rate-limit bucket if the endpoint has its own server throttle. Add error rules if it has its own codes. If it fulfils a `has: false` capability, flip it to `true` and delete its `not_supported` message. Check: `uv run python ../scripts/check_spec.py` passes.
3. **Fixture.** Add or update `fixtures/<endpoint id>.json` with the real response shape and synthetic values. Check: `uv run pytest tests/test_fixtures.py tests/test_spec.py` passes.
4. **Generate.** `uv run python ../scripts/gen_python.py`. Check: `tests/test_generated.py` passes.
5. **Tests first.** Write failing tests: a parser test in `tests/core/test_parse.py` with exact expected values, and a client test (in `test_public.py`, `test_trading.py` or `test_wallet.py`) asserting the exact request sent and the parsed result. A write endpoint also gets a sent-once-on-`NetworkError` test. Check: they fail because the method is missing.
6. **Implement.** Parser in `_core/parse.py`, unified method in `_async/client.py` with the ccxt name if ccxt has one. Then `uv run python ../scripts/gen_sync.py`. Check: the new tests pass on both clients.
7. **Docs.** Add the method to the right page in `docs/en` **and** `docs/fa`, and to `llms.txt`; if it changed a limit or capability, update `rate-limits.md` / `not-supported.md` in both languages. Run `gen_llms_full.py`. Check: `check_docs.py` prints `docs ok`.
8. **Full gate.** Run every command in `.ai/project/AGENTS.md`. Done when all are green and coverage is at least 95 %.
9. **Commit** as `feat(python): …` (or `feat(spec): …` for spec-only), listing the endpoint in the body.
