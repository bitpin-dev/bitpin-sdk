"""A minimal two-sided quoting loop. A starting point, not a strategy.

Every interval it reads the order book, quotes one bid and one ask around the mid price at
``--spread-bps``, and replaces its previous quotes (cancel by client order id, then place
both in one bulk request). It never quotes when the book is empty.

    python examples/python/market_maker.py --symbol USDT/IRT --size 10 \\
        --spread-bps 20 --iterations 3
    ... --live     # really place orders
"""

from __future__ import annotations

import sys
import time
import uuid
from collections.abc import Callable
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from _common import dry_run, parser, show

from bitpin_sdk import Bitpin, Config, errors


def quotes(mid: Decimal, spread_bps: Decimal, tick: Decimal) -> tuple[Decimal, Decimal]:
    half = mid * spread_bps / Decimal(20000)
    bid = (mid - half).quantize(tick, rounding=ROUND_DOWN)
    ask = (mid + half).quantize(tick, rounding=ROUND_UP)
    return bid, ask


def main(argv: list[str] | None = None, *, sleep: Callable[[float], object] = time.sleep) -> int:
    args = parser(__doc__ or "", writes=True)
    args.add_argument("--symbol", default="USDT/IRT")
    args.add_argument("--size", required=True, help="amount per quote, in the base currency")
    args.add_argument("--spread-bps", type=Decimal, default=Decimal(20))
    args.add_argument("--interval", type=float, default=5.0)
    args.add_argument("--iterations", type=int, default=10)
    opts = args.parse_args(argv)

    run = f"mm-{uuid.uuid4().hex[:8]}"  # unique per run, so ids never collide across restarts
    with Bitpin(Config.from_env()) as client:
        client.load_markets()
        tick = client.market(opts.symbol)["precision"]["price"]
        live: list[str] = []
        try:
            for i in range(opts.iterations):
                book = client.fetch_order_book(opts.symbol, limit=1)
                if not book["bids"] or not book["asks"]:
                    print("empty book, not quoting")
                else:
                    mid = (book["bids"][0][0] + book["asks"][0][0]) / 2
                    bid, ask = quotes(mid, opts.spread_bps, tick)
                    ids = [f"{run}-{i}-bid", f"{run}-{i}-ask"]
                    orders = [
                        {
                            "symbol": opts.symbol,
                            "type": "limit",
                            "side": side,
                            "amount": opts.size,
                            "price": price,
                            "params": {"clientOrderId": cid},
                        }
                        for side, price, cid in (("buy", bid, ids[0]), ("sell", ask, ids[1]))
                    ]
                    if not opts.live:
                        dry_run("cancel_orders", identifiers=live)
                        dry_run("create_orders", orders=orders)
                        live = ids
                    else:
                        if live:
                            client.cancel_orders(identifiers=live)
                            live = []
                        try:
                            client.create_orders(orders)
                            live = ids
                        except errors.InsufficientFunds:
                            print("insufficient funds, skipping this round")
                    show("quotes", {"mid": mid, "bid": bid, "ask": ask})
                if i + 1 < opts.iterations:
                    sleep(opts.interval)
        finally:
            # Whatever ends the loop (Ctrl-C, a network error, the last iteration),
            # never leave quotes resting unattended.
            if opts.live and live:
                client.cancel_orders(identifiers=live)
    return 0


if __name__ == "__main__":
    sys.exit(main())
