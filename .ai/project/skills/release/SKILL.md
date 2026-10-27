---
name: release
description: Cut a release of one language's SDK with release-please, tags and release notes. Use when the user asks to release, publish, bump the version or write release notes.
---

# Release

Each language is a release-please component with its own version, `CHANGELOG.md` and tag: `python-v0.1.0`, later `go/v0.1.0` and `ts-v0.1.0`. The first Python release (0.1.0) also comes from a release PR: the manifest starts at 0.0.0. Versions follow SemVer; before 1.0, a breaking change bumps the minor version.

1. **Green main.** CI on `main` is green, and `sync-with-core` has been run since the last release if any endpoint changed.
2. **Commits drive notes.** release-please reads Conventional Commits since the last tag: `feat` → minor, `fix` → patch, `feat!`/`BREAKING CHANGE:` → major (minor before 1.0). Fix misleading commit subjects by editing the release PR's changelog, not history.
3. **Release PR.** The `release-please` workflow keeps a PR open per component. Review its `CHANGELOG.md`: every user-visible change is there in plain words, breaking changes say how to migrate.
4. **Ask** the user before merging the release PR. Merging creates the tag and the GitHub Release.
5. **Publish.** The release workflow builds and uploads to PyPI through trusted publishing when the release is created. TypeScript is *staged* on npm instead: a maintainer approves it on npmjs.com (or `npm stage approve <id>`) with 2FA before it goes live. Go has nothing to upload; the `go/vX.Y.Z` tag is the release. Check: the version appears on https://pypi.org/project/bitpin-sdk/ and `pip install bitpin-sdk==<version>` works in a clean environment.
6. **Announce.** Give the user the release URL and the notes, in English and Persian if they ask.

Manual fallback (no release-please): bump `python/pyproject.toml` and `__version__`, add the `CHANGELOG.md` section, commit `chore(release): python 0.x.y`, then, with approval, `git tag -a python-v0.x.y -m "..."`, push the tag and `gh release create`.
