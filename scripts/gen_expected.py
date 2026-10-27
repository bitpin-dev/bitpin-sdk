"""Write fixtures/expected.json: what every SDK must parse each fixture into.

Python is the reference. Each case names a parser, a fixture row and extra arguments; the
output is normalized so every language can compare against it:
- decimals become plain strings ("0.00000001"), the raw `info` is dropped,
- field names are compared lowercased without underscores (clientOrderId = ClientOrderID).

Run without arguments to write the file, or with --check to fail when it is stale.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))

from bitpin_sdk._core import parse  # noqa: E402
from bitpin_sdk._core.numbers import fmt_decimal  # noqa: E402

OUT = ROOT / "fixtures" / "expected.json"

# name: (parser, fixture endpoint id, path into the fixture body, extra args)
CASES: dict[str, tuple[str, str, list[Any], list[Any]]] = {
    "market": ("parse_market", "public_get_mkt_markets", [0], []),
    "market_suspended": ("parse_market", "public_get_mkt_markets", [2], []),
    "currency": ("parse_currency", "public_get_mkt_currencies", [1], []),
    "ticker": ("parse_ticker", "public_get_mkt_tickers", [0], []),
    "ticker_sparse": ("parse_ticker", "public_get_mkt_tickers", [1], []),
    "order_book": ("parse_order_book", "public_get_mth_orderbook_symbol", [], ["BTC/IRT"]),
    "trade": ("parse_trade", "public_get_mth_matches_symbol", [0], ["BTC/IRT"]),
    "my_trade": ("parse_my_trade", "private_get_odr_fills", [0], []),
    "ohlcv": ("parse_ohlcv", "public_get_mkt_candles", [0], []),
    "order_open": ("parse_order", "private_post_odr_orders", [], []),
    "order_filled": ("parse_order", "private_get_odr_orders", [1], []),
    "history_order": ("parse_history_order", "private_get_odr_order_history", ["results", 0], []),
    "bulk_orders": ("parse_bulk_orders", "private_post_odr_orders_bulk", [], []),
    "balance": ("parse_balance", "private_get_wlt_wallets", [], []),
    "trading_fee": ("parse_trading_fee", "private_get_mkt_commissions", [0], []),
    "deposit": ("parse_deposit", "private_get_wlt_deposits", [0], []),
    "withdrawal_crypto": ("parse_withdrawal", "private_get_wlt_withdraws", [0], []),
    "withdrawal_irt": ("parse_withdrawal", "private_get_wlt_withdraws", [1], []),
    "withdrawal_created": ("parse_withdrawal", "private_post_wlt_withdraws", [], []),
    "deposit_address": ("parse_deposit_address", "private_post_wlt_address", [], ["TRX"]),
    "currency_network_v2": ("parse_currency_network", "private_get_wlt_networks", [0], []),
    "currency_network_v1": ("parse_currency_network", "private_get_wlt_networks", [1], []),
    "network": ("parse_network", "public_get_mkt_networks", [1], []),
    "bank_account": ("parse_bank_account", "private_get_wlt_account_numbers", [0], []),
}


def normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return fmt_decimal(value)
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in sorted(value.items()) if k != "info"}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    return value


def fixture_row(endpoint_id: str, path: list[Any]) -> Any:
    data = json.loads((ROOT / "fixtures" / f"{endpoint_id}.json").read_text(encoding="utf-8"))[
        "body"
    ]
    for step in path:
        data = data[step]
    return data


def render() -> str:
    cases = {}
    for name, (parser, endpoint_id, path, args) in CASES.items():
        output = getattr(parse, parser)(fixture_row(endpoint_id, path), *args)
        cases[name] = {
            "parser": parser,
            "fixture": endpoint_id,
            "path": path,
            "args": args,
            "output": normalize(output),
        }
    return json.dumps(cases, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str]) -> int:
    content = render()
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != content:
            print("fixtures/expected.json is stale. Run: python scripts/gen_expected.py")
            return 1
        return 0
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(CASES)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
