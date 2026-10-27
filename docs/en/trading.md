# Trading

All trading methods need an API key.

## Place orders

```python
client.create_order(symbol, type, side, amount=None, price=None, params=None)
```

| `type` | Needs |
|---|---|
| `limit` | `amount`, `price` |
| `market` | `amount` (base) **or** `params={"quoteAmount": ...}`, not both |
| `stop_limit` | `amount`, `price` (the limit after the trigger), `params={"stopPrice": ...}` |
| `oco` | `amount`, `price`, `params={"stopPrice": ..., "takeProfitPrice": ...}` |

`params` also takes `clientOrderId` (your own id, up to you to keep unique). Unknown keys are sent as they are. The client validates the order before sending, so a missing price raises `InvalidOrder` without using your rate limit.

```python
order = client.create_order("BTC/IRT", "limit", "buy", "0.001", "3100000000",
                            {"clientOrderId": "grid-7"})
order["status"]   # "open"
```

`create_orders(orders)` places up to **10** orders in one atomic request (all or none):

```python
client.create_orders([
    {"symbol": "USDT/IRT", "type": "limit", "side": "buy", "amount": "10", "price": "90000"},
    {"symbol": "USDT/IRT", "type": "limit", "side": "sell", "amount": "10", "price": "91000"},
])
```

## Order status

| Bitpin `state` | ccxt `status` |
|---|---|
| `initial`, `active` | `open` |
| `closed`, fully filled | `closed` |
| `closed`, not fully filled | `canceled` |

`filled`, `remaining`, `cost` (quote filled) and `average` are computed from Bitpin's fields. The raw order is in `info`.

## Read orders

| Method | What |
|---|---|
| `fetch_order(id)` | one order |
| `fetch_orders(symbol, since, limit, params)` | active orders and orders closed in the last 7 days |
| `fetch_open_orders(...)` | `initial` and `active` only |
| `fetch_closed_orders(...)` | closed in the last 7 days |
| `fetch_order_history(symbol, since, until, limit, params)` | older closed orders with at least one fill; range at most 90 days; updated with a short delay |

`params` for `fetch_orders`: `side`, `type`, `state` (lists allowed), `identifier`, `ids_in`, `identifiers_in`. Pass `paginate=True` to read every page (`maxPages`, default 100). Pages use an id cursor, which the client handles for you.

## Cancel

| Method | |
|---|---|
| `cancel_order(id)` | by order id |
| `cancel_order_by_identifier(client_order_id)` | by your `clientOrderId` |
| `cancel_orders(ids=[...])` or `cancel_orders(identifiers=[...])` | up to 10; returns `{"canceled": [...], "not_canceled": [...]}` |

A successful cancel means the engine accepted it; the order closes a moment later. Confirm with `fetch_order` or `watch_orders`. Cancelling a closed order raises `InvalidOrder`.

## Your trades

`fetch_my_trades(symbol=None, since=None, limit=None)` returns fills from the **last 24 hours** with `fee` (`cost`, `currency`). A `since` older than 24 hours raises `BadRequest`; use `fetch_order_history` instead.
