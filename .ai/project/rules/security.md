# Rule: security

Read with `SECURITY.md`. These hold on every change.

- Credentials and tokens appear only in request bodies and the `Authorization` header. `repr`, logs and exceptions show `***` or nothing. Every new path that handles them gets a test asserting they don't leak.
- TLS verification stays on; URLs stay `https://` and `wss://`.
- `FileTokenStore` files are mode 0600 in a 0700 directory, named by a hash of the key.
- Write operations are never retried. A retry policy change needs a test per write endpoint.
- Withdrawals always need the user's OTP; the SDK never stores, generates or automates OTP codes.
- New dependencies: check the exact name on PyPI, prefer well-maintained packages, pin a lower and upper bound in `pyproject.toml`, and say why in the PR. Runtime dependencies stay minimal (`httpx`, plus `centrifuge-python` for the `ws` extra).
- CI workflows use pinned action versions, least-privilege `permissions:`, and PyPI trusted publishing; no long-lived tokens in secrets.
