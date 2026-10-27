"""Place a limit order with your own client order id, read it back, then cancel it.

python examples/python/place_and_cancel.py --symbol USDT/IRT --side buy --price 90000 --amount 10
... --live     # really place and cancel
"""

from __future__ import annotations

import sys
import uuid

from _common import dry_run, parser, show

from bitpin_sdk import Bitpin, Config


def main(argv: list[str] | None = None) -> int:
    args = parser(__doc__ or "", writes=True)
    args.add_argument("--symbol", default="USDT/IRT")
    args.add_argument("--side", choices=["buy", "sell"], default="buy")
    args.add_argument("--price", required=True)
    args.add_argument("--amount", required=True)
    opts = args.parse_args(argv)

    client_order_id = f"example-{uuid.uuid4().hex[:12]}"
    order_args = {
        "symbol": opts.symbol,
        "type": "limit",
        "side": opts.side,
        "amount": opts.amount,
        "price": opts.price,
        "params": {"clientOrderId": client_order_id},
    }
    if not opts.live:
        dry_run("create_order", **order_args)
        dry_run("cancel_order_by_identifier", identifier=client_order_id)
        return 0

    with Bitpin(Config.from_env()) as client:
        order = client.create_order(**order_args)
        show("created", order)
        show("fetched", client.fetch_order(order["id"]))
        client.cancel_order_by_identifier(client_order_id)
        print(f"cancel requested for {client_order_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
