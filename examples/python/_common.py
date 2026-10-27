"""Helpers shared by the examples.

Credentials come from BITPIN_API_KEY and BITPIN_SECRET_KEY. Examples that place orders or
withdraw only print what they would send, unless you pass --live.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from typing import Any


def parser(description: str, *, writes: bool) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    if writes:
        p.add_argument(
            "--live",
            action="store_true",
            help="really send orders/withdrawals (default: dry-run, print only)",
        )
    return p


def show(title: str, value: Any) -> None:
    def default(o: Any) -> str:
        return str(o) if isinstance(o, Decimal) else repr(o)

    print(f"== {title}")
    print(json.dumps(value, indent=2, ensure_ascii=False, default=default))


def dry_run(action: str, **arguments: Any) -> None:
    show(f"DRY-RUN {action} (pass --live to send)", arguments)
