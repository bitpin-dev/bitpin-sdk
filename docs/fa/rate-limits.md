# محدودیت نرخ درخواست

بیت‌پین هر گروه از endpointها را جداگانه محدود می‌کند: وقتی توکن می‌فرستید برای هر کاربر، وگرنه برای هر IP. کلاینت برای هر باکت یک پنجرهٔ لغزان نگه می‌دارد و پیش از درخواستی که از سقف رد می‌شود صبر می‌کند، تا ربات خوش‌رفتار خطای 429 نگیرد.

## مقادیر پیش‌فرض

این‌ها سقف‌های پیش‌فرض سرور هستند. حساب‌های VIP و بازارگردان معمولاً سقف بالاتری دارند. سقف واقعی خود را از بیت‌پین بپرسید و با `Config(rate_limits=...)` تنظیم کنید ([پیکربندی](configuration.md)).

| باکت | پیش‌فرض | استفاده در |
|---|---|---|
| `auth` | 3 / min | احراز هویت (برای هر IP) |
| `refresh` | 20 / min | تمدید توکن |
| `ws_info` | 10 / min | توکن وب‌سوکت |
| `market_public` | 200 / min | `fetch_markets`، `fetch_currencies`، `fetch_networks` |
| `market_suspensions` | 2 / min | `fetch_market_suspensions` |
| `tickers` | 300 / min | `fetch_tickers`، `fetch_ticker` |
| `commissions` | 10,000 / day | `fetch_trading_fees`، `fetch_trading_fee` |
| `candles` | 300 / min | `fetch_ohlcv` |
| `orderbook` | 60 / min | `fetch_order_book` |
| `matches` | 60 / min | `fetch_trades` |
| `order_create` | 18,000 / hour | `create_order` |
| `order_read` | 18,000 / hour | `fetch_orders`، `fetch_order`، سفارش‌های باز و بسته |
| `order_cancel` | 18,000 / hour | `cancel_order`، `cancel_order_by_identifier` |
| `order_bulk_create` | 1,800 / hour | `create_orders` |
| `order_bulk_cancel` | 1,800 / hour | `cancel_orders` و همچنین `create_orders` |
| `fills` | 300 / min | `fetch_my_trades` |
| `order_history` | 5 / sec | `fetch_order_history` |
| `wallet` | 60 / min | `fetch_balance`، `fetch_bank_accounts` |
| `deposit_address` | 60 / min | `fetch_deposit_address` |
| `currency_networks` | 60 / min | `fetch_currency_networks` |
| `deposits` | 60 / min | `fetch_deposits` |
| `withdraws` | 60 / min | `fetch_withdrawals`، `withdraw` |
| `withdraw_otp` | 10,000 / day | `verify_withdraw_otp`، `resend_withdraw_otp` |

بیت‌پین ثبت گروهی سفارش را از سهمیهٔ لغو گروهی هم کم می‌کند و کلاینت هم همین کار را می‌کند.

## وقتی سرور 429 می‌دهد

کلاینت خطای `RateLimitExceeded` را با `retry_after` (ثانیه) می‌دهد، اگر سرور زمان انتظار را گفته باشد. درخواست تکرارپذیر (هر GET) که `retry_after` آن ۵ ثانیه یا کمتر باشد، پس از صبر دوباره فرستاده می‌شود. ثبت سفارش و برداشت هرگز تکرار نمی‌شوند.

```python
from bitpin_sdk import errors

try:
    client.fetch_order_book("BTC/IRT")
except errors.RateLimitExceeded as exc:
    print("دوباره تلاش کنید پس از", exc.retry_after, "ثانیه")
```

## چند پروسه

محدودکننده برای هر شیء کلاینت جداگانه می‌شمارد. چند پروسه با یک کلید از یک سهمیهٔ سرور استفاده می‌کنند؛ به هر کدام سهمی بدهید، مثلاً برای سه پروسه `rate_limits={"order_create": "6000/hour"}`.

با `enable_rate_limit=False` محدودکنندهٔ سمت کلاینت خاموش می‌شود. سرور همچنان محدودیت‌هایش را اعمال می‌کند.
