# کیف پول

همهٔ متدهای کیف پول کلید API لازم دارند.

## موجودی

```python
balance = client.fetch_balance()                 # کیف پول "main"
balance["USDT"]   # {"free": Decimal, "used": Decimal, "total": Decimal}
balance["free"]   # {"USDT": ..., "IRT": ...}
client.fetch_balance({"service": "stake"})       # سرویس دیگر کیف پول
```

`free` قابل استفاده است؛ `used` در سفارش‌های باز یا برداشت‌های در جریان بلوکه شده است.

## واریز

| متد | |
|---|---|
| `fetch_currency_networks(code)` | شبکه‌های یک ارز با وضعیت واریز (`deposit`) و برداشت (`withdraw`) |
| `fetch_deposit_address(code, network)` | آدرس شما روی آن شبکه که بار اول ساخته می‌شود؛ `tag` همان memo است که برای XRP، XLM، EOS و مشابه لازم است |
| `fetch_deposits(code=None, since=None, limit=None, params)` | `status`: `ok`، `failed` یا `pending` |

## برداشت

برداشت اول ساخته می‌شود و فقط پس از تأیید با کدهای OTP فرستاده می‌شود:

```python
w = client.withdraw("USDT", "50", "T...", params={"network": "TRX"})
client.verify_withdraw_otp(w["id"], "123456")                  # اپ احراز هویت دومرحله‌ای
if not w["info"]["is_single_otp"]:
    client.verify_withdraw_otp(w["id"], "654321", second=True) # کدی که برایتان فرستاده می‌شود
```

| نوع | فراخوانی |
|---|---|
| رمزارز | `withdraw(code, amount, address, tag=None, params={"network": "TRX"})` |
| تومان (IRT) به حساب بانکی | `withdraw("IRT", amount, params={"accountNumber": id})` با `id` از `fetch_bank_accounts()` |
| انتقال فوری و رایگان به کاربر دیگر بیت‌پین | `withdraw(code, amount, params={"alternativeAddress": phone_or_email})` |

مقصدهایی که در سایت بیت‌پین به‌عنوان آدرس مطمئن ذخیره شده‌اند فقط OTP اول را لازم دارند.

| متد | |
|---|---|
| `fetch_withdrawals(code=None, since=None, limit=None, params)` | `status`: `ok`، `failed`، `canceled` یا `pending` |
| `fetch_bank_accounts()` | حساب‌های بانکی شما و وضعیت تأییدشان |
| `verify_withdraw_otp(id, otp, second=False)` | تأیید؛ کد اشتباه خطای `InvalidOTP` با `code` می‌دهد (`invalid_otp`، `otp1_already_verified`، `extra_try`) |
| `resend_withdraw_otp(id, first=True, voice_call=False)` | ارسال دوبارهٔ کد |

`extra_try` یعنی تلاش ناموفق زیاد؛ بیت‌پین برداشت را لغو می‌کند. SDK هرگز برداشت را تکرار نمی‌کند و OTP را خودکار نمی‌کند.
