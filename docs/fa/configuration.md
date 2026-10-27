# پیکربندی

هر تنظیم یک مقدار پیش‌فرض از سرور بیت‌پین دارد و همه را می‌توانید تغییر دهید.

```python
from bitpin_sdk import Bitpin, Config, RateLimit

config = Config(
    api_key="...",
    secret_key="...",
    domain="org",             # "org" (پیش‌فرض)، "ir" یا "market"
    timeout=10,               # ثانیه برای هر درخواست
    max_retries=3,            # فقط برای درخواست‌های تکرارپذیر
    enable_rate_limit=True,   # محدودکنندهٔ سمت کلاینت
    rate_limits={"orderbook": "10800/min", "order_create": RateLimit(180_000, "hour")},
    rest_url=None,            # پیش‌فرض: آدرس REST همان دامنه
    ws_url=None,              # پیش‌فرض: آدرس وب‌سوکت همان دامنه
    user_agent=None,          # پیش‌فرض: bitpin-sdk-python/<version>
    token_store=None,         # پیش‌فرض: در حافظه؛ احراز هویت را ببینید
)
client = Bitpin(config)
```

## دامنه‌ها

بیت‌پین همان API را روی سه دامنه ارائه می‌دهد. با `domain` یکی را انتخاب کنید؛ آدرس REST و وب‌سوکت با هم عوض می‌شوند:

| `domain` | REST | وب‌سوکت |
|---|---|---|
| `org` (پیش‌فرض) | `https://api.bitpin.org` | `wss://centrifugo.bitpin.org/connection/websocket` |
| `ir` | `https://api.bitpin.ir` | `wss://centrifugo.bitpin.ir/connection/websocket` |
| `market` | `https://api.bitpin.market` | `wss://centrifugo.bitpin.market/connection/websocket` |

اگر `rest_url` و `ws_url` را خودتان بدهید (مثلاً برای پروکسی)، همان‌ها به کار می‌روند. متغیر محیطی `BITPIN_DOMAIN` هم با `Config.from_env()` کار می‌کند.

## چهار روش ساختن پیکربندی

```python
Config(api_key="...", secret_key="...")                     # در کد
Config.from_env(timeout=5)                                  # BITPIN_API_KEY، BITPIN_SECRET_KEY و BITPIN_DOMAIN
Config.from_file("bitpin.toml")                             # TOML، پایین را ببینید
Bitpin({"apiKey": "...", "secret": "...", "timeout": 5000}) # دیکشنری به سبک ccxt (timeout به میلی‌ثانیه)
```

`bitpin.toml`:

```toml
[bitpin]
api_key = "..."
secret_key = "..."
domain = "ir"
timeout = 10

[bitpin.rate_limits]
orderbook = "10800/min"
fills = "600/min"
```

کلیدهای ناشناخته و نام‌های ناشناختهٔ باکت محدودیت نرخ خطای `ValueError` می‌دهند تا اشتباه تایپی بی‌صدا نادیده گرفته نشود.

`client.describe()` آدرس‌ها، قابلیت‌ها، بازه‌های زمانی و محدودیت‌های نرخ مؤثر را نشان می‌دهد.
