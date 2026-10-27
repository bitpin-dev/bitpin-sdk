"""Read-only tour: markets, a ticker, the order book, and your balance if keys are set.

python examples/python/quickstart.py --symbol BTC/IRT
"""

from __future__ import annotations

import sys

from _common import parser, show

from bitpin_sdk import Bitpin, Config


def main(argv: list[str] | None = None) -> int:
    args = parser(__doc__ or "", writes=False)
    args.add_argument("--symbol", default="BTC/IRT")
    opts = args.parse_args(argv)

    config = Config.from_env()
    with Bitpin(config) as client:
        markets = client.load_markets()
        print(f"{len(markets)} markets, e.g. {', '.join(list(markets)[:5])}")
        show(f"ticker {opts.symbol}", client.fetch_ticker(opts.symbol))
        book = client.fetch_order_book(opts.symbol, limit=5)
        show("best bid / ask", {"bid": book["bids"][:1], "ask": book["asks"][:1]})
        if config.has_credentials:
            balance = client.fetch_balance()
            show("non-zero balances", {k: v for k, v in balance["total"].items() if v})
        else:
            print("Set BITPIN_API_KEY and BITPIN_SECRET_KEY to see your balance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
