# شروع سریع

## ۱. ساخت کلید API

در سایت یا اپ بیت‌پین بخش API را باز کنید و یک جفت کلید بسازید. بیت‌پین **کلید مخفی (secret) را فقط یک بار** نشان می‌دهد؛ آن را در یک secrets manager نگه دارید. هر کلید به فهرستی از IPهای مجاز گره خورده است؛ IP سروری را که ربات روی آن اجرا می‌شود اضافه کنید.

## ۲. نصب

```bash
pip install bitpin-sdk            # پایتون ۳٫۱۰ به بالا
pip install "bitpin-sdk[ws]"      # اگر استریم وب‌سوکت لازم دارید
```

## ۳. داده‌های عمومی (بدون کلید)

```python
from bitpin_sdk import Bitpin

with Bitpin() as client:
    markets = client.load_markets()             # {"BTC/IRT": Market, ...}
    ticker = client.fetch_ticker("BTC/IRT")
    book = client.fetch_order_book("BTC/IRT", limit=20)
    candles = client.fetch_ohlcv("BTC/IRT", "1h", limit=100)
```

## ۴. حساب شما

کلید را در کد، فایل TOML یا متغیرهای محیطی بدهید ([پیکربندی](configuration.md) را ببینید):

```python
from bitpin_sdk import Bitpin, Config

client = Bitpin(Config.from_env())   # BITPIN_API_KEY و BITPIN_SECRET_KEY
balance = client.fetch_balance()
print(balance["IRT"])                # {"free": Decimal(...), "used": ..., "total": ...}
```

## ۵. معامله

```python
order = client.create_order("USDT/IRT", "limit", "buy", "10", "90000",
                            {"clientOrderId": "my-bot-1"})
client.fetch_order(order["id"])
client.cancel_order_by_identifier("my-bot-1")
```

## ۶. ناهمگام (async)

```python
import asyncio
from bitpin_sdk import AsyncBitpin, Config

async def main() -> None:
    async with AsyncBitpin(Config.from_env()) as client:
        ticker, book = await asyncio.gather(
            client.fetch_ticker("BTC/IRT"), client.fetch_order_book("BTC/IRT"))
        update = await client.watch_order_book("BTC/IRT")   # وب‌سوکت

asyncio.run(main())
```

بیشتر: [داده‌های بازار](market-data.md)، [معامله](trading.md)، [کیف پول](wallet.md)، [وب‌سوکت](websocket.md) و [مثال‌های اجرایی](https://github.com/bitpin-dev/bitpin-sdk/tree/main/examples/python).
