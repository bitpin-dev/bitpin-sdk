# WebSocket

Streams use Bitpin's Centrifugo server and need the extra: `pip install "bitpin-sdk[ws]"`. They work with `AsyncBitpin` only. The sync `Bitpin` raises `NotSupported` for `watch_*`.

Each `watch_*` call subscribes the first time, then returns the next update. Updates that arrive between calls are queued, so a loop doesn't miss any:

```python
async with AsyncBitpin(Config.from_env()) as client:
    while True:
        book = await client.watch_order_book("BTC/IRT")
        print(book["bids"][0], book["asks"][0])
```

| Method | Channel | Returns |
|---|---|---|
| `watch_ticker(symbol)` | `market:<symbol>` | `Ticker` (24h stats) on every trade |
| `watch_ohlcv(symbol, timeframe="1m")` | `market:<symbol>` | the latest candles of that timeframe (every 10 s and on trades) |
| `watch_order_book(symbol)` | `orderbook:<symbol>` | `OrderBook` when the book changes |
| `watch_trades(symbol)` | `matches:<symbol>` | `[Trade]`, new public trades |
| `watch_orders(symbol=None)` | your private channel | `Order` when one of yours is created, filled or cancelled |
| `watch_my_trades(symbol=None)` | your private channel | `Trade`, each of your fills |

Private channels need a key. The client gets the connection token and your channel name from `POST /api/v1/usr/ws-info/` (10 per minute) and renews the token when the connection does.

Recommended pattern: read the initial state over REST (`fetch_order_book`, `fetch_open_orders`), then apply WebSocket updates. Bitpin pushes only on change.

One connection carries every channel. `await client.close()` closes it. For more control, use `bitpin_sdk.ws.BitpinWS(client, queue_size=1000)` directly.
