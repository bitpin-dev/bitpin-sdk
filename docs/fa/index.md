# SDK بیت‌پین

SDK رسمی API صرافی [بیت‌پین](https://bitpin.ir). برای بازارگردان‌ها، معامله‌گران VIP و ایجنت‌های هوش مصنوعی‌ای ساخته شده که ربات‌هایشان را می‌نویسند.

- **پایتون، هم همگام (sync) و هم ناهمگام (async).** `Bitpin` و `AsyncBitpin` متدهای یکسانی دارند. نسخه‌های Go و TypeScript در برنامه است.
- **هم‌شکل با ccxt.** نام متدها و ساختار خروجی‌ها مثل [ccxt](https://github.com/ccxt/ccxt) است؛ ربات‌های ccxt با تغییر کمی منتقل می‌شوند. [مهاجرت از ccxt](migrating-from-ccxt.md) را ببینید.
- **اعداد دقیق.** قیمت‌ها و مقدارها از نوع `decimal.Decimal` هستند و هیچ‌وقت از float عبور نمی‌کنند.
- **پیش‌فرض‌های امن.** توکن‌ها خودکار نگه‌داری و تمدید می‌شوند، کلاینت زیر محدودیت نرخ بیت‌پین می‌ماند و فقط درخواست‌های تکرارپذیر دوباره فرستاده می‌شوند. سفارش و برداشت هرگز تکرار نمی‌شوند.
- **شفاف دربارهٔ کمبودها.** قابلیت‌هایی که بیت‌پین فعلاً ندارد خطای `NotSupported` با پیام روشن می‌دهند. [فعلاً موجود نیست](not-supported.md) را ببینید.

```bash
pip install bitpin-sdk          # REST
pip install "bitpin-sdk[ws]"    # + استریم وب‌سوکت
```

```python
from bitpin_sdk import Bitpin

with Bitpin({"apiKey": "...", "secret": "..."}) as client:
    print(client.fetch_ticker("BTC/IRT")["last"])
    order = client.create_order("USDT/IRT", "limit", "buy", "10", "90000")
    client.cancel_order(order["id"])
```

قدم بعد: [شروع سریع](quickstart.md).

!!! warning "محیط آزمایشی وجود ندارد"
    بیت‌پین testnet ندارد. هر درخواست با پول واقعی به صرافی واقعی می‌رسد. مثال‌ها تا وقتی `--live` ندهید فقط درخواست را چاپ می‌کنند.
