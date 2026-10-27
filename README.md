# Bitpin SDK

[![CI](https://github.com/bitpin-dev/bitpin-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/bitpin-dev/bitpin-sdk/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/bitpin-sdk)](https://pypi.org/project/bitpin-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/bitpin-sdk)](https://pypi.org/project/bitpin-sdk/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**English** · [فارسی](README.fa.md) · [Documentation](https://bitpin-dev.github.io/bitpin-sdk/)

The official SDK for the [Bitpin](https://bitpin.ir) exchange API, for market makers, VIP traders, and the AI agents that write their bots.

- Python (sync `Bitpin`, async `AsyncBitpin`), TypeScript (`@bitpin-dev/bitpin-sdk` on npm) and Go (`github.com/bitpin-dev/bitpin-sdk/go`), all in this repository.
- ccxt method names and result structures, so a ccxt bot ports with small changes.
- `Decimal` for every price and amount.
- Tokens cached and refreshed for you; the client stays under Bitpin's rate limits, which you can override with your VIP limits.
- Orders and withdrawals are never retried automatically.
- WebSocket streams (`watch_ticker`, `watch_order_book`, `watch_orders`, …).
- Features Bitpin doesn't offer yet raise `NotSupported` with a clear message.

```bash
pip install bitpin-sdk          # add [ws] for WebSocket
```

```python
from bitpin_sdk import Bitpin, Config

with Bitpin(Config.from_env()) as client:          # BITPIN_API_KEY, BITPIN_SECRET_KEY
    book = client.fetch_order_book("USDT/IRT")
    order = client.create_order("USDT/IRT", "limit", "buy", "10", "90000",
                                {"clientOrderId": "bot-1"})
    client.cancel_order_by_identifier("bot-1")
```

> [!WARNING]
> Bitpin has no sandbox. Every call is real. The [examples](examples/python) only print what they would send unless you pass `--live`.

## Repository

| Path | What |
|---|---|
| [`spec/bitpin.yaml`](spec/bitpin.yaml) | The API description every language is generated and tested against: endpoints, rate limits, errors, capabilities |
| [`fixtures/`](fixtures) | Response samples shared by all languages' tests |
| [`python/`](python) | The Python SDK ([changelog](python/CHANGELOG.md)) |
| [`ts/`](ts) | The TypeScript SDK, npm `@bitpin-dev/bitpin-sdk` ([changelog](ts/CHANGELOG.md), [guide](docs/en/typescript.md)) |
| [`go/`](go) | The Go SDK, `github.com/bitpin-dev/bitpin-sdk/go` ([changelog](go/CHANGELOG.md), [guide](docs/en/go.md)) |
| [`examples/`](examples) | Runnable examples in Python and TypeScript, including a market-maker skeleton |
| [`docs/en`](docs/en), [`docs/fa`](docs/fa) | The documentation site, in English and Persian |
| [`AGENTS.md`](AGENTS.md), [`.ai/project/`](.ai/project) | Instructions, rules and skills for AI coding agents |
| [`llms.txt`](llms.txt) | A compact reference for AI agents that use the SDK |

## AI agents

Point your coding agent at [`llms.txt`](llms.txt) (or [`llms-full.txt`](llms-full.txt)) and the [`bitpin-trading-bot`](.ai/project/skills/bitpin-trading-bot/SKILL.md) skill. Agents working *on* this repository start at [`AGENTS.md`](AGENTS.md).

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [REVIEW.md](REVIEW.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

MIT licensed.
