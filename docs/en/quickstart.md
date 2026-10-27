# Quickstart

## 1. Create an API key

In the Bitpin website or app, open the API section and create a key pair. Bitpin shows the **secret key once**; store it in a secrets manager. Each key is bound to a list of allowed IPs, so add the IP of the server that runs your bot.

## 2. Install

```bash
pip install bitpin-sdk            # Python 3.10+
pip install "bitpin-sdk[ws]"      # if you need WebSocket streams
```

## 3. Public data (no key needed)

```python
from bitpin_sdk import Bitpin

with Bitpin() as client:
    markets = client.load_markets()             # {"BTC/IRT": Market, ...}
    ticker = client.fetch_ticker("BTC/IRT")
    book = client.fetch_order_book("BTC/IRT", limit=20)
    candles = client.fetch_ohlcv("BTC/IRT", "1h", limit=100)
```

## 4. Your account

Pass the key in code, a TOML file or environment variables (see [Configuration](configuration.md)):

```python
from bitpin_sdk import Bitpin, Config

client = Bitpin(Config.from_env())   # BITPIN_API_KEY, BITPIN_SECRET_KEY
balance = client.fetch_balance()
print(balance["IRT"])                # {"free": Decimal(...), "used": ..., "total": ...}
```

## 5. Trade

```python
order = client.create_order("USDT/IRT", "limit", "buy", "10", "90000",
                            {"clientOrderId": "my-bot-1"})
client.fetch_order(order["id"])
client.cancel_order_by_identifier("my-bot-1")
```

## 6. Async

```python
import asyncio
from bitpin_sdk import AsyncBitpin, Config

async def main() -> None:
    async with AsyncBitpin(Config.from_env()) as client:
        ticker, book = await asyncio.gather(
            client.fetch_ticker("BTC/IRT"), client.fetch_order_book("BTC/IRT"))
        update = await client.watch_order_book("BTC/IRT")   # WebSocket

asyncio.run(main())
```

More: [Market data](market-data.md), [Trading](trading.md), [Wallet](wallet.md), [WebSocket](websocket.md), and the runnable [examples](https://github.com/bitpin-dev/bitpin-sdk/tree/main/examples/python).
