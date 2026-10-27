# Contributing

Thanks for helping. Bitpin users trade real money with this SDK, so changes are held to a high bar: every behaviour has a test, and the review checklist in [REVIEW.md](REVIEW.md) applies to every PR.

## Setup

```bash
git clone https://github.com/bitpin-dev/bitpin-sdk && cd bitpin-sdk/python
uv sync
uv run pytest
```

[uv](https://docs.astral.sh/uv/) manages Python and dependencies. All commands are listed in [`.ai/project/AGENTS.md`](.ai/project/AGENTS.md).

## How changes flow

1. **Spec first.** Endpoints, limits, errors and capabilities live in [`spec/bitpin.yaml`](spec/bitpin.yaml). Change it, then run `uv run python ../scripts/gen_python.py`.
2. **Tests first.** Write a failing test, then the code. Client tests run against both the sync and async clients.
3. **Async only.** Edit `python/src/bitpin_sdk/_async/`, then `uv run python ../scripts/gen_sync.py`. Don't edit `_sync/` or `_generated/` by hand.
4. **Both languages.** User docs live in `docs/en` and `docs/fa`; `scripts/check_docs.py` checks they match.

The [`add-endpoint`](.ai/project/skills/add-endpoint/SKILL.md) skill walks through all of it.

## Commits and PRs

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(python): …`, `fix(spec): …`, `docs: …`. The PR title is checked and becomes the release note. Releases are cut by release-please; see the [`release`](.ai/project/skills/release/SKILL.md) skill.

## AI agents

Agents start at [AGENTS.md](AGENTS.md). The same rules apply to their changes, and a human maintainer approves every merge.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
