<div dir="rtl">

# SDK بیت‌پین

[English](README.md) · **فارسی** · [مستندات](https://bitpin-dev.github.io/bitpin-sdk/fa/)

SDK رسمی API صرافی [بیت‌پین](https://bitpin.ir)، برای بازارگردان‌ها، معامله‌گران VIP و ایجنت‌های هوش مصنوعی‌ای که ربات‌هایشان را می‌نویسند.

- پایتون (`Bitpin` همگام و `AsyncBitpin` ناهمگام)، تایپ‌اسکریپت (بستهٔ `@bitpin-dev/bitpin-sdk` در npm)، Go (`github.com/bitpin-dev/bitpin-sdk/go`) و جاوا (`io.github.bitpin-dev:bitpin-sdk` در Maven Central)، همه در همین مخزن.
- نام متدها و ساختار خروجی مثل ccxt است؛ ربات‌های ccxt با تغییر کمی منتقل می‌شوند.
- همهٔ قیمت‌ها و مقدارها `Decimal` هستند.
- توکن‌ها خودکار نگه‌داری و تمدید می‌شوند؛ کلاینت زیر محدودیت نرخ بیت‌پین می‌ماند و می‌توانید سقف VIP خود را تنظیم کنید.
- سفارش و برداشت هرگز خودکار تکرار نمی‌شوند.
- استریم وب‌سوکت (`watch_ticker`، `watch_order_book`، `watch_orders` و…).
- قابلیت‌هایی که بیت‌پین فعلاً ندارد خطای `NotSupported` با پیام روشن می‌دهند.

</div>

```bash
pip install bitpin-sdk          # برای وب‌سوکت [ws] را اضافه کنید
```

```python
from bitpin_sdk import Bitpin, Config

with Bitpin(Config.from_env()) as client:          # BITPIN_API_KEY و BITPIN_SECRET_KEY
    book = client.fetch_order_book("USDT/IRT")
    order = client.create_order("USDT/IRT", "limit", "buy", "10", "90000",
                                {"clientOrderId": "bot-1"})
    client.cancel_order_by_identifier("bot-1")
```

<div dir="rtl">

> [!WARNING]
> بیت‌پین محیط آزمایشی ندارد و هر درخواست واقعی است. [مثال‌ها](examples/python) تا وقتی `--live` ندهید فقط درخواست را چاپ می‌کنند.

## ساختار مخزن

| مسیر | چه چیزی |
|---|---|
| [`spec/bitpin.yaml`](spec/bitpin.yaml) | توصیف API که همهٔ زبان‌ها از روی آن ساخته و آزموده می‌شوند |
| [`fixtures/`](fixtures) | نمونه پاسخ‌های مشترک برای تست همهٔ زبان‌ها |
| [`python/`](python) | SDK پایتون ([تغییرات](python/CHANGELOG.md)) |
| [`ts/`](ts) | SDK تایپ‌اسکریپت، بستهٔ `@bitpin-dev/bitpin-sdk` در npm ([تغییرات](ts/CHANGELOG.md)، [راهنما](docs/fa/typescript.md)) |
| [`go/`](go) | SDK زبان Go، ماژول `github.com/bitpin-dev/bitpin-sdk/go` ([تغییرات](go/CHANGELOG.md)، [راهنما](docs/fa/go.md)) |
| [`java/`](java) | SDK جاوا، `io.github.bitpin-dev:bitpin-sdk` در Maven Central ([تغییرات](java/CHANGELOG.md)، [راهنما](docs/fa/java.md)) |
| [`examples/`](examples) | مثال‌های اجرایی پایتون و تایپ‌اسکریپت، از جمله اسکلت یک ربات بازارگردان |
| [`docs/en`](docs/en)، [`docs/fa`](docs/fa) | سایت مستندات به انگلیسی و فارسی |
| [`AGENTS.md`](AGENTS.md)، [`.ai/project/`](.ai/project) | دستورالعمل‌ها، قواعد و مهارت‌ها برای ایجنت‌های کدنویس |
| [`llms.txt`](llms.txt) | مرجع فشرده برای ایجنت‌هایی که از SDK استفاده می‌کنند |

## ایجنت‌های هوش مصنوعی

ایجنت خود را به [`llms.txt`](llms.txt) (یا [`llms-full.txt`](llms-full.txt)) و مهارت [`bitpin-trading-bot`](.ai/project/skills/bitpin-trading-bot/SKILL.md) ارجاع دهید. ایجنت‌هایی که روی خود این مخزن کار می‌کنند از [`AGENTS.md`](AGENTS.md) شروع می‌کنند.

## مشارکت و امنیت

[CONTRIBUTING.md](CONTRIBUTING.md) و [REVIEW.md](REVIEW.md) را ببینید. آسیب‌پذیری‌ها را طبق [SECURITY.md](SECURITY.md) به‌صورت خصوصی گزارش کنید.

مجوز MIT.

</div>
