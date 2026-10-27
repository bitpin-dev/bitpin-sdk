# Wallet

All wallet methods need an API key.

## Balance

```python
balance = client.fetch_balance()                 # the "main" wallet
balance["USDT"]   # {"free": Decimal, "used": Decimal, "total": Decimal}
balance["free"]   # {"USDT": ..., "IRT": ...}
client.fetch_balance({"service": "stake"})       # another wallet service
```

`free` is usable; `used` is frozen in open orders or pending withdrawals.

## Deposits

| Method | |
|---|---|
| `fetch_currency_networks(code)` | the networks of one currency, with `deposit` / `withdraw` availability |
| `fetch_deposit_address(code, network)` | your address on that network, created on first use; `tag` is the memo, needed for XRP, XLM, EOS and similar |
| `fetch_deposits(code=None, since=None, limit=None, params)` | `status`: `ok`, `failed` or `pending` |

## Withdrawals

A withdrawal is created first and sent only after you confirm it with OTP codes:

```python
w = client.withdraw("USDT", "50", "T...", params={"network": "TRX"})
client.verify_withdraw_otp(w["id"], "123456")                  # authenticator app
if not w["info"]["is_single_otp"]:
    client.verify_withdraw_otp(w["id"], "654321", second=True) # code sent to you
```

| Kind | Call |
|---|---|
| Crypto | `withdraw(code, amount, address, tag=None, params={"network": "TRX"})` |
| Toman (IRT) to your bank | `withdraw("IRT", amount, params={"accountNumber": id})`, with an `id` from `fetch_bank_accounts()` |
| Instant, free transfer to another Bitpin user | `withdraw(code, amount, params={"alternativeAddress": phone_or_email})` |

Destinations saved as trusted addresses on the Bitpin website need only the first OTP.

| Method | |
|---|---|
| `fetch_withdrawals(code=None, since=None, limit=None, params)` | `status`: `ok`, `failed`, `canceled` or `pending` |
| `fetch_bank_accounts()` | your bank accounts and their verification state |
| `verify_withdraw_otp(id, otp, second=False)` | confirm; a wrong code raises `InvalidOTP` with `code` (`invalid_otp`, `otp1_already_verified`, `extra_try`) |
| `resend_withdraw_otp(id, first=True, voice_call=False)` | send the code again |

`extra_try` means too many wrong codes; Bitpin cancels the withdrawal. The SDK never retries a withdrawal and never automates OTP.
