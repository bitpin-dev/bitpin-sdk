# معامله

همهٔ متدهای معامله کلید API لازم دارند.

## ثبت سفارش

```python
client.create_order(symbol, type, side, amount=None, price=None, params=None)
```

| `type` | لازم دارد |
|---|---|
| `limit` | `amount`، `price` |
| `market` | `amount` (ارز پایه) **یا** `params={"quoteAmount": ...}`، نه هر دو |
| `stop_limit` | `amount`، `price` (قیمت محدود پس از فعال‌شدن)، `params={"stopPrice": ...}` |
| `oco` | `amount`، `price`، `params={"stopPrice": ..., "takeProfitPrice": ...}` |

`params` کلید `clientOrderId` (شناسهٔ دلخواه شما که یکتا نگه‌داشتنش با خودتان است) را هم می‌گیرد. کلیدهای ناشناخته همان‌طور فرستاده می‌شوند. کلاینت پیش از ارسال سفارش را بررسی می‌کند؛ مثلاً نبودن قیمت بدون مصرف سهمیهٔ نرخ خطای `InvalidOrder` می‌دهد.

```python
order = client.create_order("BTC/IRT", "limit", "buy", "0.001", "3100000000",
                            {"clientOrderId": "grid-7"})
order["status"]   # "open"
```

`create_orders(orders)` تا **۱۰** سفارش را در یک درخواست اتمی ثبت می‌کند (یا همه یا هیچ):

```python
client.create_orders([
    {"symbol": "USDT/IRT", "type": "limit", "side": "buy", "amount": "10", "price": "90000"},
    {"symbol": "USDT/IRT", "type": "limit", "side": "sell", "amount": "10", "price": "91000"},
])
```

## وضعیت سفارش

| `state` بیت‌پین | `status` در ccxt |
|---|---|
| `initial`، `active` | `open` |
| `closed`، کامل پر شده | `closed` |
| `closed`، کامل پر نشده | `canceled` |

`filled`، `remaining`، `cost` (مقدار پرشده به ارز مظنه) و `average` از فیلدهای بیت‌پین محاسبه می‌شوند. سفارش خام در `info` است.

## خواندن سفارش‌ها

| متد | چه چیزی |
|---|---|
| `fetch_order(id)` | یک سفارش |
| `fetch_orders(symbol, since, limit, params)` | سفارش‌های فعال و سفارش‌های بسته‌شده در ۷ روز اخیر |
| `fetch_open_orders(...)` | فقط `initial` و `active` |
| `fetch_closed_orders(...)` | بسته‌شده در ۷ روز اخیر |
| `fetch_order_history(symbol, since, until, limit, params)` | سفارش‌های بستهٔ قدیمی‌تر با حداقل یک معامله؛ بازه حداکثر ۹۰ روز؛ با کمی تأخیر به‌روز می‌شود |

`params` برای `fetch_orders`: `side`، `type`، `state` (فهرست مجاز است)، `identifier`، `ids_in`، `identifiers_in`. با `paginate=True` همهٔ صفحه‌ها خوانده می‌شوند (`maxPages`، پیش‌فرض ۱۰۰). صفحه‌ها با نشانگر شناسه کار می‌کنند و کلاینت آن را برایتان مدیریت می‌کند.

## لغو

| متد | |
|---|---|
| `cancel_order(id)` | با شناسهٔ سفارش |
| `cancel_order_by_identifier(client_order_id)` | با `clientOrderId` شما |
| `cancel_orders(ids=[...])` یا `cancel_orders(identifiers=[...])` | تا ۱۰ سفارش؛ خروجی `{"canceled": [...], "not_canceled": [...]}` |

لغو موفق یعنی موتور معاملات درخواست را پذیرفته است؛ سفارش لحظه‌ای بعد بسته می‌شود. با `fetch_order` یا `watch_orders` مطمئن شوید. لغو سفارش بسته خطای `InvalidOrder` می‌دهد.

## معاملات شما

`fetch_my_trades(symbol=None, since=None, limit=None)` معاملات **۲۴ ساعت اخیر** را با `fee` (`cost`، `currency`) برمی‌گرداند. `since` قدیمی‌تر از ۲۴ ساعت خطای `BadRequest` می‌دهد؛ به جای آن از `fetch_order_history` استفاده کنید.
