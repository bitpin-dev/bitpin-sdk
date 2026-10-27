"""Stream the order book and trades of one market over WebSocket (needs the ws extra).

pip install "bitpin-sdk[ws]"
python examples/python/stream_orderbook.py --symbol BTC/IRT --updates 20
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from _common import parser

from bitpin_sdk import AsyncBitpin, Config


async def stream(client: AsyncBitpin, symbol: str, updates: int) -> None:
    async def books() -> None:
        for _ in range(updates):
            book = await client.watch_order_book(symbol)
            bid = book["bids"][0][0] if book["bids"] else None
            ask = book["asks"][0][0] if book["asks"] else None
            print(f"book  bid={bid} ask={ask}")

    async def trades() -> None:
        for _ in range(updates):
            for trade in await client.watch_trades(symbol):
                print(f"trade {trade['side']} {trade['amount']} @ {trade['price']}")

    await asyncio.gather(books(), trades())


def main(argv: list[str] | None = None, **client_options: Any) -> int:
    args = parser(__doc__ or "", writes=False)
    args.add_argument("--symbol", default="BTC/IRT")
    args.add_argument("--updates", type=int, default=20)
    opts = args.parse_args(argv)

    async def run() -> None:
        async with AsyncBitpin(Config.from_env(), **client_options) as client:
            await stream(client, opts.symbol, opts.updates)

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
