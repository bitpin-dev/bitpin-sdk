# Migrating from ccxt

The SDK uses ccxt's method names, arguments and result structures. A ccxt bot usually needs three changes.

## 1. The import and constructor

```python
# ccxt
import ccxt
exchange = ccxt.someexchange({"apiKey": key, "secret": secret, "enableRateLimit": True})

# Bitpin SDK
from bitpin_sdk import Bitpin
exchange = Bitpin({"apiKey": key, "secret": secret, "enableRateLimit": True})
```

Async: `ccxt.async_support` → `from bitpin_sdk import AsyncBitpin`. ccxt.pro `watch_*` → the same methods on `AsyncBitpin`.

## 2. Numbers are Decimal

Every price, amount and fee is a `decimal.Decimal`, so float arithmetic needs a change:

```python
spread = ticker["last"] * 0.001            # TypeError: Decimal * float
spread = ticker["last"] * Decimal("0.001") # ok
```

Inputs accept `Decimal`, `str`, `int` or `float`.

## 3. Bitpin-specific parameters

| ccxt | Bitpin SDK |
|---|---|
| `params={"stopPrice": x}` | same (`triggerPrice` also works) |
| OCO take-profit | `params={"takeProfitPrice": x}` |
| market buy by cost | `params={"quoteAmount": x}` (`cost` also works) |
| `fetch_deposit_address(code, {"network": n})` | same, or `fetch_deposit_address(code, n)` |
| `cancel_orders(ids)` | `cancel_orders(ids=[...])` or `cancel_orders(identifiers=[...])` |

Methods only Bitpin has: `cancel_order_by_identifier`, `fetch_order_history`, `fetch_market_suspensions`, `fetch_bank_accounts`, `fetch_currency_networks`, `fetch_networks`, `verify_withdraw_otp`, `resend_withdraw_otp`.

## What behaves differently

- `fetch_my_trades` covers only the last 24 hours. Older fills: `fetch_order_history`.
- `fetch_orders` covers active orders and orders closed in the last 7 days.
- `cancel_order` returns `{"id", "clientOrderId", "info"}`, not a full order; the order closes a moment later.
- `withdraw` creates a withdrawal that must be confirmed with OTP.
- Trading fees are ratios as in ccxt (`0.003`), converted from Bitpin's percents.
- Some ccxt features don't exist on Bitpin: see [Not available yet](not-supported.md).
