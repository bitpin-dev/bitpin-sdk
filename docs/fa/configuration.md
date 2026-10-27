# پیکربندی

هر تنظیم یک مقدار پیش‌فرض از سرور بیت‌پین دارد و همه را می‌توانید تغییر دهید.

```python
from bitpin_sdk import Bitpin, Config, RateLimit

config = Config(
    api_key="...",
    secret_key="...",
    timeout=10,               # ثانیه برای هر درخواست
    max_retries=3,            # فقط برای درخواست‌های تکرارپذیر
    enable_rate_limit=True,   # محدودکنندهٔ سمت کلاینت
    rate_limits={"orderbook": "10800/min", "order_create": RateLimit(180_000, "hour")},
    rest_url="https://api.bitpin.org",
    ws_url="wss://centrifugo.bitpin.org/connection/websocket",
    user_agent=None,          # پیش‌فرض: bitpin-sdk-python/<version>
    token_store=None,         # پیش‌فرض: در حافظه؛ احراز هویت را ببینید
)
client = Bitpin(config)
```

## چهار روش ساختن پیکربندی

```python
Config(api_key="...", secret_key="...")                     # در کد
Config.from_env(timeout=5)                                  # BITPIN_API_KEY و BITPIN_SECRET_KEY
Config.from_file("bitpin.toml")                             # TOML، پایین را ببینید
Bitpin({"apiKey": "...", "secret": "...", "timeout": 5000}) # دیکشنری به سبک ccxt (timeout به میلی‌ثانیه)
```

`bitpin.toml`:

```toml
[bitpin]
api_key = "..."
secret_key = "..."
timeout = 10

[bitpin.rate_limits]
orderbook = "10800/min"
fills = "600/min"
```

کلیدهای ناشناخته و نام‌های ناشناختهٔ باکت محدودیت نرخ خطای `ValueError` می‌دهند تا اشتباه تایپی بی‌صدا نادیده گرفته نشود.

`client.describe()` آدرس‌ها، قابلیت‌ها، بازه‌های زمانی و محدودیت‌های نرخ مؤثر را نشان می‌دهد.
