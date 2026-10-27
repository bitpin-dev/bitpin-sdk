# وب‌سوکت

استریم‌ها از سرور Centrifugo بیت‌پین استفاده می‌کنند و بستهٔ اضافه لازم دارند: `pip install "bitpin-sdk[ws]"`. فقط با `AsyncBitpin` کار می‌کنند؛ `Bitpin` همگام برای `watch_*` خطای `NotSupported` می‌دهد.

هر فراخوانی `watch_*` بار اول مشترک (subscribe) می‌شود و سپس به‌روزرسانی بعدی را برمی‌گرداند. هر watch متمایز (متد، نماد و بازهٔ زمانی) صف خودش را برای به‌روزرسانی‌هایی که بین دو فراخوانی می‌رسند دارد؛ پس حلقه چیزی را از دست نمی‌دهد و یک تسک برای هر بازار درست کار می‌کند. دو تسک که منتظر یک watch یکسان باشند به‌روزرسانی‌ها را بین خود تقسیم می‌کنند؛ برای هر watch یک مصرف‌کننده داشته باشید:

```python
async with AsyncBitpin(Config.from_env()) as client:
    while True:
        book = await client.watch_order_book("BTC/IRT")
        print(book["bids"][0], book["asks"][0])
```

| متد | کانال | خروجی |
|---|---|---|
| `watch_ticker(symbol)` | `market:<symbol>` | `Ticker` (آمار ۲۴ ساعته) با هر معامله |
| `watch_ohlcv(symbol, timeframe="1m")` | `market:<symbol>` | آخرین کندل‌های آن بازه (هر ۱۰ ثانیه و با هر معامله) |
| `watch_order_book(symbol)` | `orderbook:<symbol>` | `OrderBook` هنگام تغییر دفتر سفارش |
| `watch_trades(symbol)` | `matches:<symbol>` | `[Trade]`، معاملات جدید عمومی |
| `watch_orders(symbol=None)` | کانال خصوصی شما | `Order` وقتی یکی از سفارش‌هایتان ثبت، پر یا لغو شود |
| `watch_my_trades(symbol=None)` | کانال خصوصی شما | `Trade`، هر معاملهٔ شما |

کانال‌های خصوصی کلید لازم دارند. کلاینت توکن اتصال و نام کانال شما را از `POST /api/v1/usr/ws-info/` (۱۰ بار در دقیقه) می‌گیرد و هنگام اتصال دوباره توکن را تازه می‌کند.

الگوی پیشنهادی: وضعیت اولیه را با REST بخوانید (`fetch_order_book`، `fetch_open_orders`) و سپس به‌روزرسانی‌های وب‌سوکت را اعمال کنید. بیت‌پین فقط هنگام تغییر پیام می‌فرستد.

یک اتصال همهٔ کانال‌ها را حمل می‌کند. `await client.close()` آن را می‌بندد. برای کنترل بیشتر مستقیم از `bitpin_sdk.ws.BitpinWS(client, queue_size=1000)` استفاده کنید.
