# Authentication

You never handle tokens yourself. The client does this on the first private call:

1. `POST /api/v1/usr/authenticate/` with your `api_key` and `secret_key` returns an **access** token (about 15 minutes) and a **refresh** token (about 30 days).
2. Every private request sends `Authorization: Bearer <access>`.
3. About two minutes before the access token expires, the client calls `POST /api/v1/usr/refresh_token/` for a new one.
4. If the refresh fails or the refresh token has expired, the client authenticates again.
5. If the server answers 401 (for example, a revoked token), the client refreshes once and retries the request once.

Only one authenticate or refresh runs at a time, even with many concurrent `AsyncBitpin` calls.

## The 3-per-minute limit

Authenticate allows **3 requests per minute per IP**. A bot that restarts often, or several bots on one host, can hit it. Share tokens with a file cache:

```python
from bitpin_sdk import Bitpin, Config, FileTokenStore

client = Bitpin(Config.from_env(token_store=FileTokenStore()))
```

`FileTokenStore` writes `~/.cache/bitpin-sdk/<id>.json` with mode 0600. The id is a hash of your API key, never the key itself. For several hosts, implement the `TokenStore` protocol (`load`, `save`, `clear`) on top of Redis or similar.

## IP allow-list

Keys and the tokens they issue only work from the IPs you allowed for the key. A wrong IP returns `AuthenticationError`.

## Errors

| Problem | Exception |
|---|---|
| Wrong key or secret, IP not allowed | `AuthenticationError` |
| No key configured but a private method called | `AuthenticationError` |
| Account not allowed (for example, KYC level) | `PermissionDenied` |

Secrets and tokens never appear in `repr()`, logs or exception messages.
