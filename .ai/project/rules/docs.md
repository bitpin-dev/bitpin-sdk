# Rule: docs and examples

- Every page in `docs/en` has a twin in `docs/fa` with the same file name and the same facts. Persian pages are written for Persian readers, not machine-translated word by word; code, method names and values stay in English.
- Every public client method appears in both languages and in `llms.txt`. `scripts/check_docs.py` enforces it, plus the rate-limit and not-supported tables against the spec.
- After editing `docs/en` or `llms.txt`, run `scripts/gen_llms_full.py`.
- Examples default to dry-run: anything that places, cancels or withdraws prints the request unless `--live` is passed. Each example has a test in `python/tests/test_examples.py`.
- User-facing changes get a line in the PR description; release notes come from Conventional Commit messages.
