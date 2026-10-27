# مهاجرت از ccxt

SDK از نام متدها، آرگومان‌ها و ساختار خروجی ccxt استفاده می‌کند. ربات ccxt معمولاً سه تغییر لازم دارد.

## ۱. import و سازنده

```python
# ccxt
import ccxt
exchange = ccxt.someexchange({"apiKey": key, "secret": secret, "enableRateLimit": True})

# SDK بیت‌پین
from bitpin_sdk import Bitpin
exchange = Bitpin({"apiKey": key, "secret": secret, "enableRateLimit": True})
```

ناهمگام: `ccxt.async_support` ← `from bitpin_sdk import AsyncBitpin`. متدهای `watch_*` در ccxt.pro ← همان متدها روی `AsyncBitpin`.

## ۲. اعداد Decimal هستند

هر قیمت، مقدار و کارمزد از نوع `decimal.Decimal` است، پس محاسبات float باید عوض شوند:

```python
spread = ticker["last"] * 0.001            # TypeError: Decimal * float
spread = ticker["last"] * Decimal("0.001") # درست
```

ورودی‌ها `Decimal`، `str`، `int` یا `float` می‌پذیرند.

## ۳. پارامترهای مخصوص بیت‌پین

| ccxt | SDK بیت‌پین |
|---|---|
| `params={"stopPrice": x}` | همان (`triggerPrice` هم کار می‌کند) |
| حد سود OCO | `params={"takeProfitPrice": x}` |
| خرید بازار با مبلغ | `params={"quoteAmount": x}` (`cost` هم کار می‌کند) |
| `fetch_deposit_address(code, {"network": n})` | همان، یا `fetch_deposit_address(code, n)` |
| `cancel_orders(ids)` | `cancel_orders(ids=[...])` یا `cancel_orders(identifiers=[...])` |

متدهایی که فقط بیت‌پین دارد: `cancel_order_by_identifier`، `fetch_order_history`، `fetch_market_suspensions`، `fetch_bank_accounts`، `fetch_currency_networks`، `fetch_networks`، `verify_withdraw_otp`، `resend_withdraw_otp`.

## تفاوت‌های رفتاری

- `fetch_my_trades` فقط ۲۴ ساعت اخیر را پوشش می‌دهد. معاملات قدیمی‌تر: `fetch_order_history`.
- `fetch_orders` سفارش‌های فعال و بسته‌شده در ۷ روز اخیر را پوشش می‌دهد.
- `cancel_order` به جای سفارش کامل `{"id", "clientOrderId", "info"}` برمی‌گرداند؛ سفارش لحظه‌ای بعد بسته می‌شود.
- `withdraw` برداشتی می‌سازد که باید با OTP تأیید شود.
- کارمزدها مثل ccxt نسبت هستند (`0.003`) و از درصد بیت‌پین تبدیل می‌شوند.
- بعضی قابلیت‌های ccxt در بیت‌پین نیست: [فعلاً موجود نیست](not-supported.md).
