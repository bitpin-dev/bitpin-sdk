# Errors

Every exception derives from `bitpin_sdk.errors.BitpinError` and carries `status`, `body` (the parsed response) and `endpoint_id`. The classes follow ccxt, so existing `except` blocks keep working.

```text
BitpinError
├── ExchangeError                 the server answered with an error
│   ├── AuthenticationError       wrong key/secret, IP not allowed, token revoked
│   ├── PermissionDenied          account not allowed (e.g. KYC level)
│   ├── InsufficientFunds
│   ├── InvalidOrder              rejected order or cancel
│   ├── OrderNotFound
│   ├── BadRequest                invalid parameters
│   │   ├── BadSymbol
│   │   └── InvalidOTP            .code: invalid_otp | otp1_already_verified | extra_try
│   └── NotSupported              Bitpin doesn't offer this yet (.feature)
└── NetworkError                  the request may not have reached the server
    ├── RateLimitExceeded         .retry_after (seconds or None)
    ├── RequestTimeout
    └── ExchangeNotAvailable      5xx, maintenance
```

## What is retried

| Request | Retried on `NetworkError`? |
|---|---|
| GET requests and the deposit address | yes: up to `max_retries` with 0.5 s, 1 s, 2 s… backoff; a 429 only if `retry_after` ≤ 5 s |
| create order, bulk create, cancel, withdraw, OTP | **never** |

When `create_order` raises a `NetworkError`, the order may or may not exist. Look it up by your `clientOrderId` before placing it again:

```python
try:
    client.create_order("USDT/IRT", "limit", "buy", "10", "90000", {"clientOrderId": cid})
except errors.NetworkError:
    found = client.fetch_orders("USDT/IRT", params={"identifier": cid})
```

## How HTTP errors map

| Server | Exception |
|---|---|
| 401, or 406 on authenticate | `AuthenticationError` |
| 403 | `PermissionDenied` |
| 404 on an order | `OrderNotFound` |
| 406 `insufficent_balance` and similar | `InsufficientFunds` |
| 406 `cancel_order_not_allowed` | `InvalidOrder` |
| 400 on create order | `InvalidOrder` |
| 400 with an OTP code | `InvalidOTP` |
| other 400 / 404 | `BadRequest` |
| 429 | `RateLimitExceeded` |
| 5xx | `ExchangeNotAvailable` |

The rules live in `spec/bitpin.yaml`, so every SDK language maps errors the same way.
