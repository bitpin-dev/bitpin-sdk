# Security

## Reporting a vulnerability

Please report security problems **privately** through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Don't open a public issue.

Include what you found, how to reproduce it, and the version. We acknowledge reports within 3 working days and aim to fix critical problems within 14 days. We credit reporters in the release notes unless you prefer otherwise.

In scope: this SDK (credential handling, token storage, request sending, retries of write operations, parsing that could misstate amounts, the examples, the release pipeline). Vulnerabilities in Bitpin's exchange itself go to Bitpin's own security contact listed on bitpin.ir.

## Supported versions

| Version | Supported |
|---|---|
| latest 0.x release | yes |
| older | no; upgrade |

## What the SDK guarantees

- **Credentials** are sent only to the configured HTTPS API, in the authenticate request body and as a bearer token. They never appear in `repr()`, logs or exception messages.
- **Tokens** are kept in memory by default. `FileTokenStore` writes them with mode 0600 in a 0700 directory, under a hash of the API key.
- **Write operations** (orders, cancels, withdrawals, OTP) are never retried after a timeout or server error, so a lost response can't duplicate an order or a withdrawal. The only resend is after a 401, which the server rejected before processing.
- **Withdrawals** require your OTP codes; the SDK never stores or generates them.
- **Numbers** are exact `Decimal` values; no float rounding reaches an order.
- **TLS** verification is always on.
- **Releases** are built in GitHub Actions and published to PyPI with trusted publishing (no long-lived upload tokens).

## Your part

- Bind API keys to your servers' IPs on Bitpin.
- Keep keys in environment variables or a secrets manager, never in code or repositories.
- Run new bots in dry-run first. Bitpin has no sandbox.
