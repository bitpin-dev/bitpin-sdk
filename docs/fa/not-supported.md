# فعلاً موجود نیست

این قابلیت‌ها در ccxt هستند ولی API عمومی بیت‌پین فعلاً آن‌ها را ارائه نمی‌دهد. متدها وجود دارند، `client.has[...]` برابر `False` است و فراخوانی‌شان خطای `NotSupported` با پیام فارسی و انگلیسی می‌دهد. متأسفانه فعلاً این‌ها را نداریم:

| قابلیت ccxt | متد | به جای آن |
|---|---|---|
| `cancelAllOrders` | `cancel_all_orders` | `cancel_orders()` با حداکثر ۱۰ شناسه در هر بار |
| `editOrder` | `edit_order` | لغو و ثبت سفارش جدید |
| `fetchAccounts` | `fetch_accounts` | موجود نیست |
| `fetchLedger` | `fetch_ledger` | `fetch_deposits()`، `fetch_withdrawals()`، `fetch_my_trades()` |
| `transfer` | `transfer` | موجود نیست (انتقال بین سرویس‌های کیف پول) |
| `fetchDepositWithdrawFees` | `fetch_deposit_withdraw_fees` | کارمزد هر برداشت در خروجی آن است |
| `fetchPositions` | `fetch_positions` | معاملات اهرمی در API عمومی نیست |
| `setLeverage` | `set_leverage` | معاملات اهرمی در API عمومی نیست |
| `createDepositAddress` | `create_deposit_address` | `fetch_deposit_address()` بار اول آدرس را می‌سازد |
| `watchBalance` | `watch_balance` | `fetch_balance()` را دوره‌ای صدا بزنید |
| `watchTickers` | `watch_tickers` | `watch_ticker()` برای هر بازار یا `fetch_tickers()` |
| `sandbox` | `set_sandbox_mode` | testnet وجود ندارد؛ مثال‌ها به‌صورت آزمایشی (dry-run) اجرا می‌شوند |

این‌ها هم در API عمومی نیستند: حداقل مقدار سفارش و گام قیمت فراتر از `market["precision"]`، مدیریت کلید API، OTC و تبدیل.

```python
if client.has["editOrder"]:
    ...
```
