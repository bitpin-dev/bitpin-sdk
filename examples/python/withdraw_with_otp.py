"""Create a crypto withdrawal and confirm it with your OTP codes.

The first OTP comes from your authenticator app; the second is sent to you. Saved trusted
addresses need only the first (the response says ``is_single_otp``).

    python examples/python/withdraw_with_otp.py --currency USDT --network TRX \\
        --address T... --amount 10
    ... --live     # really withdraw (asks for the codes)
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from _common import dry_run, parser, show

from bitpin_sdk import Bitpin, Config


def main(argv: list[str] | None = None, *, ask: Callable[[str], str] = input) -> int:
    args = parser(__doc__ or "", writes=True)
    args.add_argument("--currency", required=True)
    args.add_argument("--network", required=True)
    args.add_argument("--address", required=True)
    args.add_argument("--memo")
    args.add_argument("--amount", required=True)
    opts = args.parse_args(argv)

    request = {
        "code": opts.currency,
        "amount": opts.amount,
        "address": opts.address,
        "tag": opts.memo,
        "params": {"network": opts.network},
    }
    if not opts.live:
        dry_run("withdraw", **request)
        return 0

    with Bitpin(Config.from_env()) as client:
        withdrawal = client.withdraw(**request)
        show("created (not sent until confirmed)", withdrawal)
        client.verify_withdraw_otp(withdrawal["id"], ask("Authenticator code: ").strip())
        if not withdrawal["info"].get("is_single_otp"):
            client.verify_withdraw_otp(
                withdrawal["id"], ask("Code sent to you: ").strip(), second=True
            )
        print("withdrawal confirmed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
