# Permissions

What an agent may do in this repository without asking, and what needs the user's explicit approval first. `.claude/settings.json` enforces the same policy for Claude Code.

## Allowed without asking

- Read any file except `.env*` and key files.
- Run the commands in `.ai/project/AGENTS.md`: tests, linters, type checks, generators, docs build.
- Edit code, tests, fixtures, docs and examples on a feature branch.
- Create local commits on a feature branch.

## Ask first

Say the exact command and what it changes:

- `git push`, opening or merging a PR, creating tags or GitHub releases.
- Publishing a package (PyPI, npm, Go tags).
- Changing `.github/workflows/`, `release-please-config.json`, branch protection or repository settings.
- Adding or upgrading a dependency.
- Any request to the live Bitpin API, including `pytest -m live`.
- Deleting files outside the task, or rewriting history.

## Never

- Force-push to `main`, or push secrets.
- Place orders, cancel orders or withdraw with real keys from an agent session.
