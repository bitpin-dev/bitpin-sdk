# FAQ

**Is there a testnet?**
No. Every call reaches the real exchange. Start with read-only calls and the examples' dry-run mode.

**I get `AuthenticationError` right away.**
Check that the server's public IP is on the key's allow-list, and that you didn't swap key and secret. Authenticate is limited to 3 per minute per IP; share tokens with `FileTokenStore` if you restart often.

**My VIP account has higher limits. Does the SDK know?**
No. The server doesn't publish them. Set them with `Config(rate_limits={...})`; see [Rate limits](rate-limits.md).

**Why are numbers `Decimal`?**
Float rounding breaks prices like `0.1 + 0.2`. Market makers need exact values.

**Can I use the sync client with WebSocket?**
Yes. `Bitpin.watch_*` blocks until the next update; the stream runs on one background thread that `close()` stops. Pass `timeout=` to stop waiting.

**An order timed out. Was it placed?**
Maybe. Orders are never retried automatically. Look it up by `clientOrderId` (see [Errors](errors.md)).

**Where are the raw fields?**
Every result has `info` with the server's response. Every endpoint is also callable directly, for example `client.private_get_odr_orders({...})`.

**How do I report a bug or a security problem?**
Bugs: GitHub issues. Security problems: privately, as described in [SECURITY.md](https://github.com/bitpin-dev/bitpin-sdk/blob/main/SECURITY.md).

**What's the full method list?**
`describe()` in code, or the reference pages: [Market data](market-data.md), [Trading](trading.md), [Wallet](wallet.md), [WebSocket](websocket.md). Close the client with `close()` or use it as a context manager.
