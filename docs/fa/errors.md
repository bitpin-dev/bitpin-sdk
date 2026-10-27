# خطاها

همهٔ استثناها از `bitpin_sdk.errors.BitpinError` ارث می‌برند و `status`، `body` (پاسخ پردازش‌شده) و `endpoint_id` دارند. کلاس‌ها مثل ccxt هستند و بلوک‌های `except` فعلی شما کار می‌کنند.

```text
BitpinError
├── ExchangeError                 سرور با خطا جواب داده
│   ├── AuthenticationError       کلید/secret اشتباه، IP غیرمجاز، توکن باطل
│   ├── PermissionDenied          حساب اجازه ندارد (مثلاً سطح احراز هویت)
│   ├── InsufficientFunds         موجودی کافی نیست
│   ├── InvalidOrder              سفارش یا لغو رد شد
│   ├── OrderNotFound
│   ├── BadRequest                پارامتر نامعتبر
│   │   ├── BadSymbol
│   │   └── InvalidOTP            .code: invalid_otp | otp1_already_verified | extra_try
│   └── NotSupported              بیت‌پین فعلاً این را ندارد (.feature)
└── NetworkError                  شاید درخواست به سرور نرسیده باشد
    ├── RateLimitExceeded         .retry_after (ثانیه یا None)
    ├── RequestTimeout
    └── ExchangeNotAvailable      5xx، تعمیرات
```

## چه چیزی تکرار می‌شود

| درخواست | با `NetworkError` تکرار می‌شود؟ |
|---|---|
| درخواست‌های GET و آدرس واریز | بله: تا `max_retries` با فاصلهٔ ۰٫۵، ۱، ۲… ثانیه؛ 429 فقط اگر `retry_after` ≤ ۵ ثانیه |
| ثبت سفارش، ثبت گروهی، لغو، برداشت، OTP | **هرگز**. تنها استثنا: پس از 401 (سرور پیش از هر پردازشی توکن را رد کرده) کلاینت توکن را تمدید می‌کند و درخواست را یک بار دیگر می‌فرستد |

اگر `create_order` خطای `NetworkError` بدهد، شاید سفارش ثبت شده باشد و شاید نه. پیش از ثبت دوباره، آن را با `clientOrderId` پیدا کنید:

```python
try:
    client.create_order("USDT/IRT", "limit", "buy", "10", "90000", {"clientOrderId": cid})
except errors.NetworkError:
    found = client.fetch_orders("USDT/IRT", params={"identifier": cid})
```

## نگاشت خطاهای HTTP

| سرور | استثنا |
|---|---|
| 401، یا 406 در احراز هویت | `AuthenticationError` |
| 403 | `PermissionDenied` |
| 404 روی سفارش | `OrderNotFound` |
| 406 با `insufficent_balance` و مشابه | `InsufficientFunds` |
| 406 با `cancel_order_not_allowed` | `InvalidOrder` |
| 400 در ثبت سفارش | `InvalidOrder` |
| 400 با کد OTP | `InvalidOTP` |
| سایر 400 / 404 | `BadRequest` |
| 429 | `RateLimitExceeded` |
| 5xx | `ExchangeNotAvailable` |

قواعد در `spec/bitpin.yaml` هستند تا همهٔ زبان‌های SDK خطاها را یکسان نگاشت کنند.
