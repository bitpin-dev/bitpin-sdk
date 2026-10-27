# bitpin-sdk

The official Python SDK for the [Bitpin](https://bitpin.ir) exchange API: sync `Bitpin` and async `AsyncBitpin`, ccxt method names and result structures, `Decimal` numbers, automatic token refresh, client-side rate limiting with overridable VIP limits, and WebSocket streams.

SDK رسمی پایتون برای API صرافی بیت‌پین. [مستندات فارسی](https://bitpin-dev.github.io/bitpin-sdk/fa/)

```bash
pip install bitpin-sdk          # REST
pip install "bitpin-sdk[ws]"    # + WebSocket
```

```python
from bitpin_sdk import Bitpin, Config

with Bitpin(Config.from_env()) as client:          # BITPIN_API_KEY, BITPIN_SECRET_KEY
    print(client.fetch_ticker("BTC/IRT")["last"])
    order = client.create_order("USDT/IRT", "limit", "buy", "10", "90000",
                                {"clientOrderId": "bot-1"})
    client.cancel_order_by_identifier("bot-1")
```

Bitpin has no sandbox: every call is real.

- [Documentation](https://bitpin-dev.github.io/bitpin-sdk/) (English and Persian)
- [Examples](https://github.com/bitpin-dev/bitpin-sdk/tree/main/examples/python)
- [llms.txt](https://github.com/bitpin-dev/bitpin-sdk/blob/main/llms.txt) for AI agents
- [Changelog](https://github.com/bitpin-dev/bitpin-sdk/blob/main/python/CHANGELOG.md)
- [Security](https://github.com/bitpin-dev/bitpin-sdk/blob/main/SECURITY.md)
