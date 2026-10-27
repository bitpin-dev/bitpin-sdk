# Review checklist

For every pull request, by a human or an AI reviewer. The reviewer sees the diff and the linked issue; report findings with file and line, most severe first. Correctness and safety come before style.

## Money safety (blocking)

- Write calls (create order, bulk create, cancel, withdraw, OTP) are still sent at most once. Any retry logic change has a test per write endpoint.
- Amounts and prices stay `Decimal` from input to request body; nothing goes through `float` arithmetic or `round()`.
- Validation that used to run before sending still does, and a rejected input sends nothing.
- Order status, `filled`, `remaining` and fee calculations match the tables in `docs/en/trading.md`.
- Examples and generated bots still require `--live` to write.

## Secrets and privacy (blocking)

- No key, secret or token in code, fixtures, logs, `repr` or exception text; new code paths that handle them have a leak test.
- Fixtures are synthetic. Nothing from Bitpin's private backend (paths, internal routes, user ids) is in the diff.
- New dependencies are justified, exist on PyPI under that exact name, and are bounded in `pyproject.toml`.

## Contract

- `spec/bitpin.yaml` changed first; `_generated/`, `_sync/` and `llms-full.txt` are regenerated (CI `--check` passes).
- Only `/api/` endpoints. Endpoint ids and public method names are unchanged, or the PR is marked breaking.
- ccxt names and result keys are kept where ccxt has them.
- A new capability gap is a `has: false` entry with en and fa messages.

## Tests

- New behaviour has tests that would fail without it, assert the exact request sent, and run on both clients.
- Coverage stays at or above 95 % branch.

## Docs

- User-visible changes are in `docs/en` and `docs/fa` with the same facts, and in `llms.txt` when they change the API surface.
- The PR title is a Conventional Commit; it becomes the release note.
