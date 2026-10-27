# Not available yet

These features exist in ccxt but Bitpin's public API doesn't offer them yet. The methods are there, `client.has[...]` is `False`, and calling one raises `NotSupported` with an English and a Persian message.

| ccxt capability | Method | What to do instead |
|---|---|---|
| `cancelAllOrders` | `cancel_all_orders` | `cancel_orders()` with up to 10 ids at a time |
| `editOrder` | `edit_order` | cancel, then place a new order |
| `fetchAccounts` | `fetch_accounts` | not available |
| `fetchLedger` | `fetch_ledger` | `fetch_deposits()`, `fetch_withdrawals()`, `fetch_my_trades()` |
| `transfer` | `transfer` | not available (between wallet services) |
| `fetchDepositWithdrawFees` | `fetch_deposit_withdraw_fees` | a withdrawal's fee is in its result |
| `fetchPositions` | `fetch_positions` | margin isn't offered on the public API |
| `setLeverage` | `set_leverage` | margin isn't offered on the public API |
| `createDepositAddress` | `create_deposit_address` | `fetch_deposit_address()` creates it on first use |
| `watchBalance` | `watch_balance` | poll `fetch_balance()` |
| `watchTickers` | `watch_tickers` | `watch_ticker()` per symbol, or `fetch_tickers()` |
| `sandbox` | `set_sandbox_mode` | there is no testnet; the examples run as dry-run |

Also missing from the public API: minimum order sizes and price steps beyond `market["precision"]`, API-key management, OTC and convert.

```python
if client.has["editOrder"]:
    ...
```
