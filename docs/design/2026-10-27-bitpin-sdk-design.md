# Bitpin SDK — design

Status: draft for approval · 2026-10-27 · repo `github.com/bitpin-dev/bitpin-sdk`

## 1. Why

Bitpin has a public REST + WebSocket API but no official client (`public-api-doc/docs/Introduction/guide.mdx` says one is "coming soon"). VIP traders and market makers each write their own wrapper and trip over the same problems: auth throttled at 3/min per IP, `offset` that is an id cursor and not a skip count, docs that disagree with the server, and undocumented limits.

Goal: a VIP or market maker with no prior Bitpin knowledge can install one package and trade within minutes. An AI coding agent can read the repo (or the shipped `llms.txt` and skill) and write a correct Bitpin bot on the first try.

## 2. Goals, non-goals, anti-goals

Goals
- Python first, sync and async, fully typed. Go and TypeScript later, in the same repo, against the same spec and fixtures.
- Cover every Bitpin HTTP endpoint under `/api/` that a trader needs (list in §6), plus the Centrifugo WebSocket channels.
- ccxt-shaped (owner's choice): ccxt method names, a ccxt-style constructor (`Bitpin({'apiKey': ..., 'secret': ...})` as well as `Config`), and ccxt result structures (`timestamp`, `datetime`, `fee`, `remaining`, `filled`, `free`/`used`/`total`, …), with numbers as `Decimal`. Porting a ccxt bot means changing the import plus small edits where it does float math. No float mode.
- Every endpoint that traders expect but Bitpin doesn't have raises a clear `NotSupported` ("Bitpin doesn't offer this yet"), driven by a `has` map.
- All server constants (rate limits, batch sizes, lifetimes, URLs) live in one spec with `core` defaults, and the user can override any of them through config.
- Bilingual docs (English and Persian), release notes, CI, many strict tests.
- AI-native repo: `AGENTS.md`, `.ai/project/` rules, skills and permissions, `REVIEW.md`, `SECURITY.md`.

Non-goals
- No transpiler. ccxt writes once in JS and machine-translates; for one exchange that's a large build system that yields non-idiomatic code.
- No endpoint outside `/api/` (owner's rule). The web-app routes (`/v1/`, `/v4/`, `/srv/`, `/crm/`, `/tp/`) are out, even when richer.
- No trading strategies in the package. Examples show patterns, they aren't products.
- No Go or TypeScript code in v0.1; only the repo layout that leaves room for them.

Anti-goals (would be a failure even if it technically works)
- Leaking internals of `core`: hardcoded VIP user ids, internal and test-only routes, file paths.
- An example or default that places a real order or withdrawal by accident.
- Logging or printing `api_key`, `secret_key`, or tokens.
- Silently diverging from the spec (a method whose path or limits differ from `spec/`).

## 3. Decided by the owner

- GitHub org `bitpin-dev` (created). Python first (sync + async), then Go and TypeScript.
- One repository for all languages, like ccxt, but hand-written per language (no transpiler).
- Only `/api/` endpoints. Missing features are reported as "not available yet".
- Constants and rate limits come from `core` defaults and are user-overridable via config.
- Docs in Persian and English; release notes; CI; AI-native files; extensive tests.

- Dry-run lives in the examples and the `bitpin-trading-bot` skill only: they default to dry-run and need `--live`. The SDK itself always talks to the real exchange.

## 4. What we take from ccxt, and what we don't

Taken
- A declarative exchange description (ccxt `describe()`): urls, an `api` map of endpoints, rate limits, `has` capability map, error mapping, `options`. Ours is a language-neutral file, `spec/bitpin.yaml`, so Go and TS read the same source.
- Implicit API methods generated from the endpoint map, one per endpoint (`public_get_mkt_markets`, `private_post_odr_orders`, …). Adding an endpoint is one spec entry plus regeneration.
- Unified methods with ccxt names and ccxt-shaped return dicts (each also carries the raw response under `info`).
- ccxt's exception hierarchy.
- ccxt.pro-style `watch_*` methods for WebSocket.

Not taken
- The transpiler (see non-goals).
- ccxt's single global `rateLimit` + per-call `cost`. Bitpin has many independent server-side buckets in mixed units (§7), so we model named buckets instead.
- Floats. Prices and amounts are `decimal.Decimal` in Python (market makers can't afford float rounding). ccxt-style symbols `BTC/IRT` and Bitpin ids `BTC_IRT` are both accepted; results use `BTC/IRT` with the id in `id`.

## 5. Repository layout

```
bitpin-sdk/
  AGENTS.md                 entry point for every coding agent (contributors)
  CLAUDE.md                 imports AGENTS.md and .ai/project/AGENTS.md
  REVIEW.md                 what a reviewer (human or AI) checks on every PR
  SECURITY.md               vulnerability reporting + what the SDK guarantees
  README.md / README.fa.md
  CHANGELOG is per language (python/CHANGELOG.md), written by release-please
  llms.txt / llms-full.txt  compact SDK reference for AI agents of SDK *users*
  .ai/project/
    AGENTS.md               commands, layout, conventions, gotchas; lists rules and skills
    permissions.md          what agents may do here without asking
    rules/                  spec.md, python.md, testing.md, docs.md, security.md
    skills/
      add-endpoint/         spec entry → regenerate → unified method → fixtures → tests → docs (en+fa)
      sync-with-core/       re-check spec constants against core (for maintainers with core access)
      release/              conventional commits → release-please PR → publish
      bitpin-trading-bot/   for SDK users: how to build a bot safely with this SDK
  .claude/settings.json     enforced permission allow/deny list mirroring permissions.md
  spec/
    bitpin.yaml             the single source of truth (§6–§9)
    schema.json             JSON Schema for bitpin.yaml, checked in CI
  fixtures/                 recorded-shape, synthetic JSON responses shared by all languages
  docs/
    en/ fa/                 mkdocs-material site, published to GitHub Pages
    design/                 design docs (this file)
  examples/python/          quickstart, orders, bulk, websocket, market-maker skeleton (dry-run by default)
  python/
    pyproject.toml          dist name `bitpin-sdk`, import `bitpin_sdk`
    src/bitpin_sdk/
      _generated/           endpoints + constants generated from spec/ (do not edit)
      _core/                sans-I/O: request building, response parsing, error mapping, token state, rate limiter
      _async/               AsyncBitpin: the hand-written source of truth for client logic
      _sync/                Bitpin: generated from _async/ with `unasync` (do not edit)
      ws/                   Centrifugo client (async only in v0.1)
      config.py errors.py types.py
    tests/
  go/ ts/                   later
  .github/                  workflows, issue/PR templates, CODEOWNERS, dependabot
```

Why `bitpin-sdk` / `bitpin_sdk`: the PyPI name `bitpin` belongs to an unofficial third-party package (amiwrpremium/bitpin, v0.4.3). `bitpin-sdk` is free. A distinct import name avoids clashing with it.

Why the `.ai/project/` layout: it is the layout of our internal `ai-templates` (v0.4.0), so the repo feels like every other Bitpin repo to agents. The internal `.ai/org/` content is **not** copied: it references internal accounts and systems and this repo is public.

## 6. API scope (from `core`, verified against the docs)

All paths relative to the REST base URL. Trailing slash is mandatory (`APPEND_SLASH = False`).

| Unified method | Endpoint | Auth |
|---|---|---|
| (auth, automatic) | POST `/api/v1/usr/authenticate/`, POST `/api/v1/usr/refresh_token/` | key/secret |
| (ws token, automatic) | POST `/api/v1/usr/ws-info/` | key/secret |
| `fetch_currencies` | GET `/api/v1/mkt/currencies/` | public |
| `fetch_markets` | GET `/api/v1/mkt/markets/` | public |
| `fetch_market_suspensions` (extra) | GET `/api/v1/mkt/markets/suspensions/` | private |
| `fetch_networks` (extra) | GET `/api/v1/mkt/networks/` | public |
| `fetch_tickers`, `fetch_ticker` | GET `/api/v1/mkt/tickers/` (single = filter of all) | public |
| `fetch_ohlcv` | GET `/api/v1/mkt/candles/` | public |
| `fetch_trading_fees`, `fetch_trading_fee` | GET `/api/v1/mkt/commissions/` | private |
| `fetch_order_book` | GET `/api/v1/mth/orderbook/{symbol}/` | public |
| `fetch_trades` | GET `/api/v1/mth/matches/{symbol}/` | public |
| `create_order` | POST `/api/v1/odr/orders/` | private |
| `create_orders` | POST `/api/v1/odr/orders/bulk/` (max 10) | private |
| `fetch_order` | GET `/api/v1/odr/orders/{id}/` | private |
| `fetch_orders`, `fetch_open_orders`, `fetch_closed_orders` | GET `/api/v1/odr/orders/` | private |
| `cancel_order` | DELETE `/api/v1/odr/orders/{id}/` | private |
| `cancel_order_by_identifier` (extra) | DELETE `/api/v1/odr/orders/identifier/{identifier}/` | private |
| `cancel_orders` | DELETE `/api/v1/odr/orders/bulk/` (max 10) | private |
| `fetch_my_trades` | GET `/api/v1/odr/fills/` | private |
| `fetch_order_history` (extra) | GET `/api/v1/odr/order_history/` | private |
| `fetch_balance` | GET `/api/v1/wlt/wallets/` | private |
| `fetch_bank_accounts` (extra) | GET `/api/v1/wlt/account_numbers/` | private |
| `fetch_deposit_address` | POST `/api/v2/wlt/address/` (idempotent: core returns the existing active address, creates one only if none exists, so it's safe to retry) | private |
| `fetch_currency_networks` (extra) | GET `/api/v2/wlt/networks/` | private |
| `fetch_deposits` | GET `/api/v2/wlt/deposits/` | private |
| `fetch_withdrawals` | GET `/api/v2/wlt/withdraws/` | private |
| `withdraw` | POST `/api/v2/wlt/withdraws/` | private |
| `verify_withdraw_otp` (extra) | POST `/api/v1/wlt/withdraws/verify/otp/{id}/` | private |
| `resend_withdraw_otp` (extra) | POST `/api/v1/wlt/withdraws/retry/{id}/` | private |

WebSocket (Centrifugo, `wss://centrifugo.bitpin.org/connection/websocket`): `watch_ticker` (`market:{symbol}`, `currency_price_update`), `watch_ohlcv` (`market:{symbol}`, `candle_update`), `watch_order_book` (`orderbook:{symbol}`), `watch_trades` (`matches:{symbol}`), `watch_orders` and `watch_my_trades` (`user:order_info#{user_identifier}`). The `/api/`-only rule is about HTTP paths; WebSocket channels in scope are the ones in the public docs. `tickers:all` exists in core but is undocumented, so it's out of v0.1.

Excluded on purpose: the v1 wallet routes deprecated by `/api/v2/wlt/` (address, networks, deposits, withdraws, withdraws/by-currency-code), a test-only duplicate of the orders API, an internal restricted price endpoint, GET on `ws-info`.

Not available yet (`has[...] = False`, the method raises `NotSupported` with a bilingual message): user/account info, API-key management, OTC and convert, margin and positions, cancel-all, edit order, testnet/sandbox, market order rules (min size, `price_increment`), deposit/withdraw fee lookup, transfers between services, ledger, `watch_balance`, `watch_tickers` (all-markets).

## 7. Configuration, constants and rate limits

`spec/bitpin.yaml` holds every constant with its `core` source (file:line kept in the maintainers' sync skill, **not** in the public spec). Examples: REST/WS URLs, access-token TTL 15 min, refresh TTL 30 days, bulk batch 10, orderbook max limit 50, candles max 10 000 per request, order-history max range 3 months, fills `start` no older than 24 h, page-size maxima.

Rate limits are named buckets, each `{limit, period}` with the server's default:

| Bucket | Default | Endpoints |
|---|---|---|
| `auth` | 3 / min | authenticate |
| `refresh` | 20 / min | refresh_token |
| `ws_info` | 10 / min | ws-info |
| `market_public` | 200 / min (10 000 / day when anonymous, bucket `market_public_anon`) | currencies, markets, networks |
| `market_suspensions` | 2 / min | suspensions |
| `tickers` | 300 / min | tickers |
| `commissions` | 10 000 / day | commissions |
| `candles` | 300 / min | candles |
| `orderbook` | 60 / min | orderbook |
| `matches` | 60 / min | recent trades |
| `order_create` | 18 000 / h | place order |
| `order_read` | 18 000 / h | list, get |
| `order_cancel` | 18 000 / h | cancel by id, by identifier |
| `order_bulk_create` | 1 800 / h | bulk place (also consumes `order_bulk_cancel`, as the server does) |
| `order_bulk_cancel` | 1 800 / h | bulk cancel |
| `fills` | 300 / min | fills |
| `order_history` | 5 / s | order history |
| `wallet` | 60 / min | wallets, account numbers |
| `deposit_address` | 60 / min | deposit address |
| `currency_networks` | 60 / min | currency networks |
| `deposits` | 60 / min | deposits |
| `withdraws` | 60 / min | withdraws list and create |
| `withdraw_otp` | 10 000 / day | verify / retry OTP |

The builder re-verifies every number against `core` before coding (they appear to come from `core`'s throttling modules; some docs values disagree and lose).

User override, in code or a file:

```python
from bitpin_sdk import Bitpin, Config, RateLimit

client = Bitpin(Config(
    api_key=..., secret_key=...,
    rate_limits={"orderbook": RateLimit(10_800, "min")},   # a VIP's real limit
    enable_rate_limit=True,                                # client-side limiter on (default)
    timeout=10, max_retries=3,
))
Config.from_file("bitpin.toml")   # same fields; env vars BITPIN_API_KEY / BITPIN_SECRET_KEY
```

VIP tiers in `core` are hardcoded per user, so override-by-config is the only way a VIP's client uses their real limit. The client-side limiter is advisory; a 429 is still parsed (`Expected available in N seconds`) and raised as `RateLimitExceeded(retry_after=N)`, and retried only for idempotent requests (never for create order / withdraw).

## 8. Behaviour the SDK owns

- Token lifecycle: authenticate once, cache the pair, refresh the access token proactively ~2 min before `exp`, re-authenticate only if refresh fails. Authenticate failures are 406 in `core`, mapped to `AuthenticationError`. Never more than one authenticate in flight (lock).
- Errors: ccxt hierarchy — `BitpinError` → `ExchangeError` → `AuthenticationError`, `PermissionDenied`, `InsufficientFunds`, `InvalidOrder`, `OrderNotFound`, `BadRequest`, `NotSupported`; `NetworkError` → `RateLimitExceeded`, `RequestTimeout`, `ExchangeNotAvailable`. The mapping (status + `detail`/`code` patterns) lives in the spec.
- Pagination: `offset` is "id less than", never a skip count. Unified `fetch_*` take `since`/`limit` like ccxt; `paginate=True` walks pages. `order_history` uses its cursor and resends filters on every page (server doesn't keep them).
- Orders: `state` initial/active → `open`; `closed` → `closed` if fully dealt, else `canceled` (builder confirms the rule against `core`). `identifier` is the client order id (`clientOrderId` in params). `average_price` and `suspended` are kept even though the docs omit them.
- Input validation before sending: candles need `from`/`to` (server 500s otherwise), bulk ≤ 10, fills `since` ≤ 24 h old, history range ≤ 3 months.
- Tolerant parsing where the server is inconsistent: bulk place accepts both `[...]` and `{"orders": [...]}`; v2 networks accepts the v1 shape (current server bug) and the documented v2 shape.
- Withdrawals: `withdraw()` creates and returns the id plus `is_single_otp`; the caller must call `verify_withdraw_otp()` — the SDK never automates OTP.
- Secrets are redacted in `repr`, logs and exceptions.

- Tokens are cached in a pluggable `TokenStore`: in-memory by default, plus a file store (`~/.cache/bitpin-sdk/`, mode 0600) so restarts and several processes on one host don't burn the 3/min-per-IP authenticate budget. The rate limiter is per process; docs warn that several processes share one server budget (buckets are per user when authenticated, per IP otherwise) and show how to split it with config overrides. *(builder's call)*

## 9. Sync and async without duplication

`_core/` is sans-I/O (pure functions: build request, parse response, map error) so most logic is shared and tested once. Client logic is written once in `_async/`; `_sync/` is generated by `unasync` (the approach httpx/httpcore use). CI fails if `_sync/` or `_generated/` are stale. HTTP via `httpx`. WebSocket via `centrifuge-python` (async only in v0.1).

## 10. Tests

No Bitpin sandbox exists, so CI never calls the live API.

- One test body runs against both clients (sync and async parametrized), using `respx` with responses from `fixtures/`.
- Spec-drift test: every endpoint in the spec has an implicit method, every unified method's path/method/bucket matches the spec, every fixture validates against the shape in the spec.
- `has`-map test: every `False` raises `NotSupported`; every `True` has a test.
- Error-mapping tests for every status/code in the spec; retry/backoff and 429 `retry_after` tests; token lifecycle tests with a fake clock (proactive refresh, single-flight authenticate, refresh failure → re-auth).
- Rate-limiter tests with a fake clock, including bulk-create consuming two buckets and config overrides.
- Property tests (`hypothesis`) for decimal/precision formatting and symbol conversion.
- WebSocket tests against a fake Centrifugo transport.
- Secret-redaction tests (repr, logs, exceptions).
- Examples are executed in CI against mocks (dry-run).
- Gates: ruff, mypy `--strict`, coverage ≥ 95 % branch on `python/src`.
- Optional live smoke suite (`pytest -m live`), read-only endpoints only, never in CI.

## 11. CI and releases (GitHub Actions)

- On PR: lint, mypy, tests on Python 3.10–3.13 (Linux) + 3.13 on macOS and Windows; spec schema + drift; unasync/codegen freshness; docs build (both languages) and link check; CodeQL; dependency review. Commits follow Conventional Commits (checked on the PR title).
- Releases: release-please in monorepo mode. Each language is a component with its own version, `CHANGELOG.md`, tag (`python-v0.1.0`, later `go/v0.1.0`, `ts-v0.1.0`) and GitHub Release with notes. Publishing to PyPI uses trusted publishing (the owner configures it once on PyPI).
- Dependabot for Actions and Python deps; CODEOWNERS.

## 12. Docs

mkdocs-material site with `en` and `fa` (RTL) built from `docs/en` and `docs/fa`, published to GitHub Pages: quickstart, auth, configuration and rate limits, every unified method, WebSocket, errors, "not available yet", migrating from ccxt, FAQ. README in both languages. Every user-facing page exists in both languages; CI fails if a page is missing in one.

## 13. Calls I made (owner can overturn)

- Repo `bitpin-dev/bitpin-sdk`, **public** (needed for VIPs and PyPI). Initial push only after the owner says go.
- PyPI dist `bitpin-sdk`, import `bitpin_sdk`, classes `Bitpin` / `AsyncBitpin`.
- Decimal everywhere, ccxt `BTC/IRT` symbols in results.
- License MIT.
- Minimum Python 3.10.
- Docs site on GitHub Pages; release-please; unasync.
- English is the default doc language; Persian is a full mirror.
- Where docs and `core` disagree, `core` wins.

- The builder has read access to `core` and verifies every constant there first; no live probing of production. Fixtures are built from `core`'s serializers and the docs examples, with synthetic values.

## 14. Left to the builder

Internal module names, test file layout, exact fixture contents (synthetic, no real customer data), example bot logic, docs page order, mkdocs theme details.
