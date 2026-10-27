# Bitpin SDK (Python v0.1.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `bitpin-sdk` 0.1.0 for Python (sync + async, REST + WebSocket) in the `bitpin-dev/bitpin-sdk` monorepo, with spec, fixtures, bilingual docs, CI, releases and AI-native files.

**Architecture:** `spec/bitpin.yaml` is the single source of truth; a generator writes `python/src/bitpin_sdk/_generated/spec.py`. Pure sans-I/O logic lives in `_core/`; client logic is hand-written once in `_async/` and `_sync/` is generated with `unasync`. ccxt names and result shapes, `Decimal` numbers.

**Tech Stack:** Python ≥3.10, httpx, PyYAML (dev/codegen only), centrifuge-python, pytest, pytest-asyncio, respx, hypothesis, ruff, mypy, unasync, mkdocs-material + mkdocs-static-i18n, release-please, GitHub Actions.

**Spec:** `docs/design/2026-10-27-bitpin-sdk-design.md`

## Global Constraints

- Only HTTP paths under `/api/`. Trailing slash on every path.
- REST base `https://api.bitpin.org`, WS `wss://centrifugo.bitpin.org/connection/websocket`.
- Dist `bitpin-sdk`, import `bitpin_sdk`, classes `Bitpin` (sync) / `AsyncBitpin`.
- Numbers are `decimal.Decimal`; ccxt symbols `BTC/IRT` in results, accept `BTC/IRT` or `BTC_IRT` in input.
- No float mode. No dry-run in the SDK. Never auto-retry non-idempotent calls (create order, bulk create, cancel, withdraw, OTP).
- Never log/print/repr `secret_key`, `api_key`, tokens. No real customer data in fixtures. No core internals (user ids, file paths, internal routes) in the public repo.
- Python 3.10–3.13. mypy `--strict`. Branch coverage ≥ 95 % on `python/src`.
- Every user doc page exists in `docs/en` and `docs/fa`.
- Conventional Commits. Tag `python-v0.1.0`.

## Constants verified in core (2026-10-27)

Rate-limit buckets (`limit/period`): `auth` 3/min (per IP) · `refresh` 20/min · `ws_info` 10/min · `market_public` 200/min authenticated, `market_public_anon` 10000/day anonymous (currencies, markets, networks) · `market_suspensions` 2/min · `tickers` 300/min · `commissions` 10000/day · `candles` 300/min · `orderbook` 60/min · `matches` 60/min · `order_create` 18000/h · `order_read` 18000/h (list, get) · `order_cancel` 18000/h (by id, by identifier) · `order_bulk_create` 1800/h · `order_bulk_cancel` 1800/h (bulk POST consumes both) · `fills` 300/min · `order_history` 5/s · `wallet` 60/min (wallets, account_numbers) · `deposit_address` 60/min · `currency_networks` 60/min · `deposits` 60/min · `withdraws` 60/min · `withdraw_otp` 10000/day (verify, retry).

Other: access TTL 900 s, refresh TTL 30 d, bulk max 10, orderbook `limit` max 50 (default 20), candles max 10000, order history range ≤ 90 days, history `limit` 1–200 default 50, fills `start` ≥ now−24 h, orders page max 250, fills page max 250, wallets page max 1000.

Errors: 401 → `AuthenticationError`; 406 on authenticate/ws-info → `AuthenticationError`; 403 → `PermissionDenied`; 404 → `OrderNotFound` on order paths else `BadRequest`; 406 with detail `insufficent_balance`/`insufficent_frozen`/`insufficent_pool_balance` → `InsufficientFunds`; 406 `cancel_order_not_allowed`/"not allowed" → `InvalidOrder`; other 406 → `ExchangeError`; 400 on order paths → `InvalidOrder`, else `BadRequest`; 429 → `RateLimitExceeded(retry_after)` parsed from `Expected available in N seconds`; 5xx/503 → `ExchangeNotAvailable`; httpx timeout → `RequestTimeout`; other transport errors → `NetworkError`. OTP codes `invalid_otp`, `otp1_already_verified`, `extra_try` → `InvalidOTP(code)` (subclass of `BadRequest`).

## Review Focus

- Many coroutines hit an expired token at once → exactly one authenticate/refresh call (test in Task 5).
- A 429 or timeout on `create_order` → raised, never retried (test in Task 7).
- `Decimal("1E-8")`, floats and ints as amounts → sent as plain strings `"0.00000001"`, no exponent, no float rounding (test in Task 4).
- Symbols `btc/irt`, `BTC_IRT`, `BTC/IRT` → all normalize to id `BTC_IRT`; unknown separators raise `BadSymbol` (test in Task 4).
- JWT with malformed/absent `exp` → treated as expired and refreshed, not a crash (test in Task 5).

---

### Task 1: Repo skeleton, spec and spec schema

**Files:**
- Create: `spec/bitpin.yaml`, `spec/schema.json`, `scripts/check_spec.py`, `python/pyproject.toml`, `python/src/bitpin_sdk/__init__.py`, `python/src/bitpin_sdk/py.typed`, `python/tests/test_spec.py`, `.gitignore`, `LICENSE` (MIT, "Bitpin"), `.editorconfig`

**Interfaces:**
- Produces: `spec/bitpin.yaml` top-level keys `version, urls{rest,ws}, constants{...}, rate_limits{name:{limit:int,period:sec|min|hour|day}}, endpoints{id:{method,path,auth:public|private|credentials,buckets:[...],idempotent:bool,docs}}, errors{...}, has{name:true|false}, not_supported{name:{en,fa}}, ws{channels{...}}`. Endpoint ids are ccxt implicit style: `public_get_mkt_currencies`, `private_post_odr_orders`, `private_delete_odr_orders_id`, `credentials_post_usr_authenticate`, …

- [ ] **Step 1:** Write `python/tests/test_spec.py::test_spec_validates_against_schema`, `test_every_endpoint_path_starts_with_api_and_ends_with_slash`, `test_every_endpoint_bucket_exists`, `test_every_has_false_has_bilingual_message`, `test_no_deprecated_v1_wallet_paths` (asserts `/api/v1/wlt/address/`, `/api/v1/wlt/networks/`, `/api/v1/wlt/deposits/`, `/api/v1/wlt/withdraws/` absent).
- [ ] **Step 2:** Run `cd python && pytest tests/test_spec.py` → FAIL (no spec).
- [ ] **Step 3:** Write spec with every endpoint from design §6 and the constants/buckets/errors above; JSON Schema with `additionalProperties: false`.
- [ ] **Step 4:** Run tests → PASS. `python scripts/check_spec.py` exits 0.
- [ ] **Step 5:** Commit `chore: scaffold monorepo and add API spec`.

### Task 2: Code generation from spec

**Files:**
- Create: `scripts/gen_python.py`, `python/src/bitpin_sdk/_generated/__init__.py`, `python/src/bitpin_sdk/_generated/spec.py`, `python/tests/test_generated.py`

**Interfaces:**
- Produces in `_generated/spec.py` (no YAML at runtime): `URLS: dict[str,str]`, `CONSTANTS: dict[str,int]`, `RATE_LIMITS: dict[str, tuple[int, str]]`, `ENDPOINTS: dict[str, Endpoint]` where `Endpoint` is a frozen dataclass `(id, method, path, auth, buckets: tuple[str,...], idempotent: bool)`, `HAS: dict[str,bool]`, `NOT_SUPPORTED: dict[str, tuple[str,str]]`, `WS_CHANNELS: dict[str,str]`.
- `scripts/gen_python.py --check` exits 1 if the file is stale.

- [ ] **Step 1:** Tests: `test_generated_is_fresh` (runs generator in check mode), `test_endpoints_match_yaml`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement generator (sorted, deterministic output, header "generated — do not edit"). **Step 4:** PASS. **Step 5:** Commit `feat(python): generate endpoint table from spec`.

### Task 3: Errors and error mapping

**Files:** Create `python/src/bitpin_sdk/errors.py`, `python/src/bitpin_sdk/_core/errors.py`, `python/tests/core/test_errors.py`

**Interfaces:**
- Produces: hierarchy `BitpinError → ExchangeError → {AuthenticationError, PermissionDenied, InsufficientFunds, InvalidOrder, OrderNotFound, BadRequest → {BadSymbol, InvalidOTP}, NotSupported}`; `BitpinError → NetworkError → {RateLimitExceeded(retry_after: float|None), RequestTimeout, ExchangeNotAvailable}`. Every error has `.status: int|None`, `.body: Any`, `.endpoint_id: str|None`.
- `map_error(endpoint_id: str, status: int, body: Any) -> BitpinError` (pure).

- [ ] **Step 1:** Parametrized `test_map_error` with one case per row of "Errors" above (status, endpoint, body → class, retry_after). Plus `test_not_supported_message_is_bilingual`.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `feat(python): error hierarchy and mapping`.

### Task 4: Config, rate limiter, symbols, decimals

**Files:** Create `python/src/bitpin_sdk/config.py`, `_core/ratelimit.py`, `_core/symbols.py`, `_core/numbers.py`, `_core/redact.py`; tests `tests/core/test_config.py`, `test_ratelimit.py`, `test_symbols.py`, `test_numbers.py`

**Interfaces:**
- `RateLimit(limit: int, period: Literal["sec","min","hour","day"])` frozen dataclass.
- `Config(api_key=None, secret_key=None, rest_url=URLS["rest"], ws_url=URLS["ws"], timeout=10.0, max_retries=3, enable_rate_limit=True, rate_limits: Mapping[str, RateLimit] = {}, token_store: TokenStore|None=None, user_agent: str|None=None)`; `Config.from_ccxt(dict)` (keys `apiKey`, `secret`, `timeout` in ms, `enableRateLimit`, `options.rateLimits`), `Config.from_file(path)` (TOML, `[bitpin]` table, `[bitpin.rate_limits] orderbook = "10800/min"`), `Config.from_env()` (`BITPIN_API_KEY`, `BITPIN_SECRET_KEY`); `Config.rate_limit(bucket) -> RateLimit` = override or default; unknown bucket name in overrides raises `ValueError`. `repr` shows `api_key='***'`.
- `SlidingWindowLimiter(rules: Mapping[str,RateLimit], clock: Callable[[], float])`: `delay(buckets: Sequence[str]) -> float` (seconds to wait, 0 if free) and `record(buckets)`. Pure; clients do the sleeping.
- `to_market_id(symbol: str) -> str`, `to_symbol(market_id: str) -> str`; raise `BadSymbol`.
- `to_decimal(x: str|int|float|Decimal|None) -> Decimal|None` (float via `repr`), `fmt_decimal(x) -> str` (no exponent, strip trailing zeros).

- [ ] **Step 1:** Tests: overrides incl. ccxt dict and TOML; limiter with fake clock (3/min: 4th call delayed until oldest + 60 s; two buckets → max delay); Review Focus symbol and decimal cases; hypothesis round-trip `to_decimal(fmt_decimal(d)) == d`; redaction of `repr(Config)`.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `feat(python): config, rate limiter, symbol and decimal helpers`.

### Task 5: Token lifecycle and token stores

**Files:** Create `_core/auth.py`, `python/src/bitpin_sdk/token_store.py`; tests `tests/core/test_auth.py`, `tests/test_token_store.py`

**Interfaces:**
- `Tokens(access: str, refresh: str, access_exp: float, refresh_exp: float)`; `jwt_exp(token: str) -> float|None` (base64 payload decode, no verification).
- `TokenState(clock)`: `action() -> Literal["ok","refresh","authenticate"]` (refresh when `now >= access_exp - 120`, authenticate when no tokens or refresh expired), `set_tokens(data: dict)`, `set_access(data: dict)`.
- `TokenStore` Protocol `load(key_id: str) -> Tokens|None`, `save(key_id, Tokens)`, `clear(key_id)`; `MemoryTokenStore`, `FileTokenStore(dir=~/.cache/bitpin-sdk)` writing files mode 0600, key_id = sha256(api_key)[:16] (never the key itself).
- Single-flight is enforced in the clients (Task 7) with one lock around the `action()` → network → `set_*` section.

- [ ] **Step 1:** Tests: state transitions with fake clock; malformed/absent `exp` → `authenticate`; file store perms 0600 and filename contains no api_key; store round-trip.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `feat(python): token lifecycle and token stores`.

### Task 6: Request building and response parsers

**Files:** Create `_core/request.py`, `_core/parse.py`, `python/src/bitpin_sdk/types.py`, `fixtures/*.json` (one per endpoint, synthetic, shapes from core serializers); tests `tests/core/test_request.py`, `tests/core/test_parse.py`, `tests/test_fixtures.py`

**Interfaces:**
- `Request(method, url, params: dict|None, json: Any|None, endpoint_id, buckets, auth, idempotent)`; `build_request(config, endpoint_id, path_params: dict, params: dict|None, body: Any|None) -> Request` (GET → query, else JSON; lists in query comma-joined; `Decimal` → `fmt_decimal`; booleans `true/false`).
- `types.py`: `TypedDict`s with ccxt field names — `Market, Currency, Ticker, OrderBook, Trade, OHLCV (list[int|Decimal]), Order, Balances, TradingFee, Deposit, Withdrawal, DepositAddress, Network, BankAccount`. Each includes `info: dict`.
- Parsers `parse_market`, `parse_currency`, `parse_ticker`, `parse_order_book`, `parse_trade`, `parse_my_trade`, `parse_ohlcv`, `parse_order`, `parse_history_order`, `parse_balance(list)`, `parse_trading_fee`, `parse_deposit`, `parse_withdrawal`, `parse_deposit_address`, `parse_currency_network` (accepts v1 and v2 shapes), `parse_bulk_orders` (accepts `[...]` and `{"orders": [...]}`).
- Order status rule: `initial|active` → `open`; `closed` and `dealed_base_amount >= base_amount` (or market by quote with `dealed_quote_amount >= quote_amount`) → `closed`; other `closed` → `canceled`. `remaining = amount - filled`. ISO datetimes → `timestamp` ms + `datetime` UTC ISO.

- [ ] **Step 1:** Tests: `test_fixtures_validate` (each endpoint has a fixture), one parser test per fixture with exact expected dicts, order status table, Review Focus decimal serialization in bodies.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `feat(python): request builder, parsers and shared fixtures`.

### Task 7: Async client — transport, implicit API, public market data

**Files:** Create `_async/client.py`, `_async/__init__.py`; tests `tests/conftest.py` (fixture `client` parametrized over `["async","sync"]`, async test bodies only — a `run()` helper awaits or calls), `tests/test_transport.py`, `tests/test_public.py`

**Interfaces:**
- `AsyncBitpin(config: Config | Mapping | None = None, *, http_client: httpx.AsyncClient|None=None, clock=time.monotonic, sleep=asyncio.sleep)`; async context manager; `close()`.
- `request(endpoint_id, path_params=None, params=None, body=None) -> Any`: rate-limit delay → auth (single-flight lock) → send → map errors → retry only if `idempotent` and error is `NetworkError` (not `RateLimitExceeded` unless `retry_after` ≤ 5 s), max `max_retries`, exponential backoff 0.5·2ⁿ. On 401 for a private call: clear tokens, re-authenticate once, retry once.
- Implicit methods generated as attributes from `ENDPOINTS`: `await client.public_get_mkt_tickers()`.
- Unified: `load_markets(reload=False)`, `fetch_markets()`, `fetch_currencies()`, `fetch_networks(params)`, `fetch_ticker(symbol)`, `fetch_tickers(symbols=None)`, `fetch_order_book(symbol, limit=None)`, `fetch_trades(symbol)`, `fetch_ohlcv(symbol, timeframe="30m", since=None, limit=None, params)` (computes `from`/`to`; requires since or limit; rejects > 10000), `fetch_trading_fees()`, `fetch_trading_fee(symbol)`, `fetch_market_suspensions()`. `has` property and `describe()`.

- [ ] **Step 1:** Tests: implicit method exists for every endpoint id; headers (`Authorization: Bearer`, `User-Agent: bitpin-sdk-python/<version>`); Review Focus: `create_order` 429/timeout not retried (`respx` call count 1); idempotent GET retried on 503; 401 → one re-auth; concurrent `gather` of 10 private calls with expired token → authenticate called once; public parsers end-to-end; ohlcv validation.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `feat(python): async client with public market data`.

### Task 8: Async client — trading, account, wallet, NotSupported

**Files:** Modify `_async/client.py`; tests `tests/test_trading.py`, `tests/test_wallet.py`, `tests/test_has.py`

**Interfaces:**
- `create_order(symbol, type, side, amount=None, price=None, params={})` (params: `stopPrice`/`stop_price`, `ocoTargetPrice`, `clientOrderId`→`identifier`, `quoteAmount`); `create_orders(orders: list[dict])` (≤10, else `BadRequest` before sending); `fetch_order(id)`; `fetch_orders(symbol=None, since=None, limit=None, params)`; `fetch_open_orders`; `fetch_closed_orders`; `cancel_order(id)`; `cancel_order_by_identifier(identifier)`; `cancel_orders(ids=None, identifiers=None)` returns `{"canceled": [...], "not_canceled": [...]}`; `fetch_my_trades(symbol=None, since=None, limit=None)` (rejects since older than 24 h); `fetch_order_history(symbol=None, since=None, until=None, limit=None, params)` with `paginate=True` cursor walk resending filters.
- `fetch_balance()` → ccxt `{"BTC": {"free","used","total"}, "free": {...}, "used": {...}, "total": {...}, "info"}` (paged over all wallets, `service` param default `main`); `fetch_bank_accounts()`; `fetch_deposit_address(code, network)`; `fetch_currency_networks(code)`; `fetch_deposits(code=None, since=None, limit=None)`; `fetch_withdrawals(...)`; `withdraw(code, amount, address=None, tag=None, params)` (params `network`, `accountNumber`, `alternativeAddress`); `verify_withdraw_otp(id, otp, second=False)`; `resend_withdraw_otp(id, first=True)`.
- Every `has[x] is False` name exists as a method raising `NotSupported`.
- `paginate` uses id-cursor `offset` = smallest id seen.

- [ ] **Step 1:** Tests per method: request shape (method, path, body/query exact) and parsed result; bulk > 10 rejected locally; bulk consumes both buckets; `has` table test; pagination walk stops on short page.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `feat(python): trading, wallet and not-supported methods`.

### Task 9: Sync client via unasync

**Files:** Create `scripts/gen_sync.py`, generated `_sync/client.py`, `_sync/__init__.py`; modify `__init__.py` exports; test `tests/test_sync_fresh.py`

**Interfaces:** `Bitpin` mirrors `AsyncBitpin` (httpx.Client, `time.sleep`, `threading.Lock`). `gen_sync.py --check` fails if stale.

- [ ] **Step 1:** `test_sync_is_fresh`; switch `client` fixture to run every existing test on both clients.
- [ ] **Steps 2–5:** FAIL → generate → full suite PASS on both → commit `feat(python): generate sync client with unasync`.

### Task 10: WebSocket (async)

**Files:** Create `ws/__init__.py`, `ws/client.py`, `ws/parse.py`; tests `tests/ws/test_ws.py` with a fake transport

**Interfaces:**
- `BitpinWS(client: AsyncBitpin, *, transport_factory=None)`; `watch_ticker(symbol)`, `watch_ohlcv(symbol, timeframe="1m")`, `watch_order_book(symbol)`, `watch_trades(symbol)`, `watch_orders(symbol=None)`, `watch_my_trades(symbol=None)` — each an async iterator. Also `AsyncBitpin.watch_*` delegating to a lazily created `BitpinWS`.
- Private channels fetch `ws_token` + `user_identifier` via `credentials_post_usr_ws_info`; on token expiry reconnect with a new token. Channel names from `WS_CHANNELS`.

- [ ] **Step 1:** Tests: channel name per method; parse each event (`currency_price_update`, `candle_update`, `market_data`, `matches_update`, `user_order_update`, `user_match_update`) into the ccxt types; private subscribe obtains token; symbol filter on `watch_orders`.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `feat(python): websocket watch methods`.

### Task 11: Examples

**Files:** `examples/python/{quickstart.py, place_and_cancel.py, bulk_orders.py, stream_orderbook.py, market_maker.py, withdraw_with_otp.py}`; test `python/tests/test_examples.py`

Every example that writes takes `--live`; without it, it prints the request it would send and exits 0. `market_maker.py`: quote both sides around mid with spread/size args, cancel/replace by `identifier`, watch fills.

- [ ] **Step 1:** `test_examples_dry_run` runs each with mocked HTTP, asserts no write request sent without `--live`.
- [ ] **Steps 2–5:** FAIL → implement → PASS → commit `docs(examples): add dry-run examples`.

### Task 12: Docs (en + fa), READMEs, llms.txt

**Files:** `mkdocs.yml`, `docs/en/*.md`, `docs/fa/*.md` (index, quickstart, authentication, configuration, rate-limits, market-data, trading, wallet, websocket, errors, not-supported, migrating-from-ccxt, faq, changelog link), `README.md`, `README.fa.md`, `llms.txt`, `llms-full.txt`, `scripts/check_docs.py` (en/fa parity + every unified method appears in docs + rate-limit table generated from spec matches)

- [ ] **Step 1:** `tests/test_docs.py` calling `check_docs.py`. **Step 2:** FAIL. **Step 3:** write docs. **Step 4:** PASS and `mkdocs build --strict` OK. **Step 5:** commit `docs: bilingual documentation and llms.txt`.

### Task 13: AI-native files

**Files:** `AGENTS.md`, `CLAUDE.md`, `REVIEW.md`, `SECURITY.md`, `.ai/project/AGENTS.md`, `.ai/project/permissions.md`, `.ai/project/rules/{spec,python,testing,docs,security}.md`, `.ai/project/skills/{add-endpoint,sync-with-core,release,bitpin-trading-bot}/SKILL.md`, `.claude/settings.json`, `.github/copilot-instructions.md` (points to AGENTS.md)

- [ ] **Step 1:** `tests/test_ai_files.py`: each skill/rule listed in `.ai/project/AGENTS.md` exists; every SKILL.md has `name`/`description` frontmatter; settings.json denies reading `.env*`, `git push --force`.
- [ ] **Steps 2–5:** FAIL → write → PASS → commit `docs(ai): agent instructions, rules, skills and permissions`.

### Task 14: CI, release automation, repo hygiene

**Files:** `.github/workflows/{ci.yml, docs.yml, release-please.yml, publish-python.yml, codeql.yml, pr-title.yml}`, `release-please-config.json`, `.release-please-manifest.json` (`{"python": "0.0.0"}` → first release 0.1.0), `.github/dependabot.yml`, `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/{bug,feature}.yml`, `.github/pull_request_template.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `python/CHANGELOG.md`, `.pre-commit-config.yaml`

ci.yml jobs: lint (ruff check + format check), types (mypy --strict), test matrix (3.10–3.13 ubuntu; 3.13 macos/windows) with coverage gate, spec (schema, gen --check, gen_sync --check), docs (check_docs + mkdocs build --strict). Publish uses PyPI trusted publishing, runs on `python-v*` release.

- [ ] **Step 1:** `actionlint` passes locally (or `python -c yaml.safe_load` if actionlint missing). **Step 2:** full local gate: `ruff check`, `mypy --strict`, `pytest --cov --cov-branch --cov-fail-under=95`. **Step 3:** commit `ci: add workflows and release automation`.

### Task 15: Publish

- [ ] **Step 1:** Fresh-context review of the whole branch (security + correctness). Fix findings.
- [ ] **Step 2:** Ask owner to confirm, then `gh repo create bitpin-dev/bitpin-sdk --public`, push `main`, enable Pages.
- [ ] **Step 3:** Tag `python-v0.1.0` with release notes from `python/CHANGELOG.md`; GitHub Release. PyPI publish only after owner configures trusted publishing.
