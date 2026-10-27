# bitpin-sdk: project instructions

A monorepo of hand-written SDKs for Bitpin's public API, one per language, all generated from and tested against one spec. Python is the first language; Go and TypeScript will join under `go/` and `ts/`.

## Layout

```
spec/bitpin.yaml     single source of truth: endpoints, rate limits, constants, errors, has map
fixtures/            one synthetic response per endpoint, replayed by every language's tests
python/src/bitpin_sdk/
  _generated/        from spec by scripts/gen_python.py        (generated)
  _core/             sans-I/O: requests, parsers, errors, auth state, limiter
  _async/            AsyncBitpin, the hand-written client
  _sync/             Bitpin, from _async by scripts/gen_sync.py (generated; _compat.py is hand-written)
  ws/                WebSocket (Centrifugo), async only
docs/en, docs/fa     the docs site; every page exists in both languages
examples/python/     runnable examples, dry-run unless --live
```

## Commands

Run from `python/` (uv manages the environment):

```bash
uv sync                                        # install
uv run pytest                                  # tests (both clients)
uv run pytest --cov                            # coverage gate: 95 % branch
uv run ruff check src tests ../examples && uv run ruff format --check src tests ../examples
uv run mypy src ../examples/python             # strict
uv run python ../scripts/check_spec.py         # spec schema
uv run python ../scripts/gen_python.py         # after editing spec/bitpin.yaml
uv run python ../scripts/gen_sync.py           # after editing _async/
uv run python ../scripts/gen_llms_full.py      # after editing docs/en
uv run python ../scripts/check_docs.py         # en/fa parity, every method documented
uvx --with-requirements ../docs/requirements.txt mkdocs build --strict -f ../mkdocs.yml
```

Each generator has `--check`; CI runs them all, so a stale generated file fails the build.

## Conventions

- Unified methods use ccxt names, arguments and result structures. Bitpin-only methods get plain names (`fetch_order_history`, `verify_withdraw_otp`).
- Numbers are `Decimal` end to end; requests carry plain decimal strings.
- Client logic lives in `_async/client.py` only; regenerate `_sync/`.
- Anything Bitpin lacks is a `has: false` entry with an en+fa message in the spec, plus a method raising `not_supported(...)`.
- Conventional Commits; PR titles are checked. Scopes: `python`, `spec`, `docs`, `ci`, `examples`.
- English for code, comments and commits; user docs in English and Persian.

## Gotchas

- `offset` in Bitpin lists means "ids below this", not a row count.
- Authenticate is limited to 3 per minute per IP: tests must never let the client re-authenticate in a loop.
- Bitpin's English and Persian API docs disagree in places. The server behaviour wins; `sync-with-core` is how maintainers confirm it.
- There is no sandbox. Tests mock HTTP with respx; `pytest -m live` is read-only and never runs in CI.

## Rules

Read the rule that matches your task before editing:

| Rule | Read when |
|---|---|
| `.ai/project/rules/spec.md` | changing `spec/`, `fixtures/`, endpoints, limits or errors |
| `.ai/project/rules/python.md` | changing `python/` |
| `.ai/project/rules/testing.md` | writing or changing tests |
| `.ai/project/rules/docs.md` | changing `docs/`, READMEs, `llms.txt` or examples |
| `.ai/project/rules/security.md` | touching auth, tokens, withdrawals, logging, dependencies or CI |

Permissions (what needs the user's approval): `.ai/project/permissions.md`. Reviews follow `REVIEW.md`; vulnerabilities follow `SECURITY.md`.

## Skills

When a task matches, open the skill and follow it:

| Skill | Use when |
|---|---|
| `.ai/project/skills/add-endpoint/SKILL.md` | adding or changing an API endpoint, field or error |
| `.ai/project/skills/sync-with-core/SKILL.md` | re-checking spec constants and shapes against Bitpin's server |
| `.ai/project/skills/release/SKILL.md` | cutting a release or writing release notes |
| `.ai/project/skills/bitpin-trading-bot/SKILL.md` | writing a trading bot or strategy that uses this SDK |
