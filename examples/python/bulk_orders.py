"""Place a ladder of up to 10 limit orders in one atomic request, then cancel them in bulk.

    python examples/python/bulk_orders.py --symbol USDT/IRT --side buy \\
        --top 90000 --step 100 --count 5 --amount 10
"""

from __future__ import annotations

import sys
from decimal import Decimal

from _common import dry_run, parser, show

from bitpin_sdk import Bitpin, Config


def ladder(
    symbol: str, side: str, top: Decimal, step: Decimal, count: int, amount: str
) -> list[dict[str, object]]:
    direction = -1 if side == "buy" else 1
    return [
        {
            "symbol": symbol,
            "type": "limit",
            "side": side,
            "amount": amount,
            "price": top + direction * step * i,
        }
        for i in range(count)
    ]


def main(argv: list[str] | None = None) -> int:
    args = parser(__doc__ or "", writes=True)
    args.add_argument("--symbol", default="USDT/IRT")
    args.add_argument("--side", choices=["buy", "sell"], default="buy")
    args.add_argument("--top", type=Decimal, required=True, help="price of the first order")
    args.add_argument("--step", type=Decimal, required=True, help="price distance between orders")
    args.add_argument("--count", type=int, default=5, choices=range(1, 11))
    args.add_argument("--amount", required=True)
    opts = args.parse_args(argv)

    orders = ladder(opts.symbol, opts.side, opts.top, opts.step, opts.count, opts.amount)
    if not opts.live:
        dry_run("create_orders", orders=orders)
        return 0

    with Bitpin(Config.from_env()) as client:
        created = client.create_orders(orders)
        show("created", [(o["id"], o["price"]) for o in created])
        show("cancel", client.cancel_orders(ids=[o["id"] for o in created]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
