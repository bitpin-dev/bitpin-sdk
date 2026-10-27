# داده‌های بازار

متدهای عمومی کلید API لازم ندارند. نماد بازار به شکل `BTC/IRT` نوشته می‌شود؛ `BTC_IRT` و حروف کوچک هم کار می‌کنند.

| متد | خروجی |
|---|---|
| `load_markets(reload=False)` | `{symbol: Market}`، روی کلاینت کش می‌شود |
| `market(symbol)` | یک `Market` از کش (اول `load_markets()` را صدا بزنید) |
| `fetch_markets()` | `[Market]` با `precision` (گام قیمت و مقدار) و `active` |
| `fetch_currencies()` | `{code: Currency}` |
| `fetch_networks(params)` | همهٔ شبکه‌ها؛ فیلترهای `code`، `can_deposit`، `can_withdraw` |
| `fetch_tickers(symbols=None)` | `{symbol: Ticker}` |
| `fetch_ticker(symbol)` | `Ticker`: `last`، `high`، `low`، `percentage` (تغییر ۲۴ ساعته به درصد) |
| `fetch_order_book(symbol, limit=None)` | `{"bids": [[price, amount]], "asks": ...}`؛ پیش‌فرض ۲۰ سطر، حداکثر ۵۰ |
| `fetch_trades(symbol, since=None, limit=None)` | معاملات اخیر عمومی، از قدیمی به جدید |
| `fetch_ohlcv(symbol, timeframe="30m", since=None, limit=None)` | `[[ms, open, high, low, close, volume]]` |
| `fetch_trading_fees()` / `fetch_trading_fee(symbol)` | کارمزد میکر/تیکر شما به نسبت (`0.003` یعنی ۰٫۳٪)؛ کلید لازم است |
| `fetch_market_suspensions()` | `{symbol: suspended}` برای حساب شما؛ کلید لازم است، ۲ بار در دقیقه |
| `describe()` | قابلیت‌ها، بازه‌های زمانی، آدرس‌ها و محدودیت‌های نرخ مؤثر |
| `request(endpoint_id, path_params, params=, body=)` | فراخوانی سطح پایین هر endpoint |

## کندل‌ها

بازه‌ها: `1m 5m 15m 30m 1h 3h 4h 6h 1d 1w 1M` (`1m` یک دقیقه و `1M` یک ماه). بدون `since` آخرین `limit` کندل را می‌گیرید (پیش‌فرض ۵۰۰). هر درخواست حداکثر ۱۰٬۰۰۰ کندل برمی‌گرداند. بازهٔ ناشناخته خطای `BadRequest` می‌دهد؛ سرور بی‌صدا `30m` را به کار می‌برد.

## دقت

`market["precision"]["price"]` و `["amount"]` گام‌ها به شکل `Decimal` هستند، مثلاً `Decimal("1")` برای قیمت تومانی و `Decimal("1E-8")` برای مقدار بیت‌کوین. قیمت‌ها را پیش از ثبت سفارش با این گام‌ها گرد کنید.

## API ضمنی

هر endpoint یک متد هم‌نام با شناسه‌اش در spec هم دارد که یک دیکشنری می‌گیرد (پارامترهای مسیر از روی نام جدا می‌شوند):

```python
client.public_get_mth_orderbook_symbol({"symbol": "BTC_IRT", "limit": 50})
client.private_get_odr_orders({"state": "active"})
```

این‌ها JSON خام برمی‌گردانند. متدهای یکپارچه را ترجیح دهید؛ این‌ها برای فیلدهایی است که متدهای یکپارچه نشان نمی‌دهند.
