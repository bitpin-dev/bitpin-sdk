"""Convert between ccxt symbols (``BTC/IRT``) and Bitpin market ids (``BTC_IRT``)."""

from __future__ import annotations

import re

from bitpin_sdk.errors import BadSymbol

_PART = re.compile(r"^[A-Z0-9]+$")


def _split(value: str, sep: str) -> tuple[str, str] | None:
    parts = value.split(sep)
    if len(parts) != 2 or not all(_PART.match(p) for p in parts):
        return None
    return parts[0], parts[1]


def to_market_id(symbol: str) -> str:
    """``"btc/irt"``, ``"BTC/IRT"`` or ``"BTC_IRT"`` → ``"BTC_IRT"``."""
    value = symbol.strip().upper()
    for sep in ("/", "_"):
        if sep in value:
            parts = _split(value, sep)
            if parts:
                return f"{parts[0]}_{parts[1]}"
    raise BadSymbol(f"invalid symbol {symbol!r}; use 'BASE/QUOTE', e.g. 'BTC/IRT'")


def to_symbol(market_id: str) -> str:
    """``"BTC_IRT"`` → ``"BTC/IRT"``."""
    parts = _split(market_id, "_")
    if parts is None:
        raise BadSymbol(f"invalid market id {market_id!r}")
    return f"{parts[0]}/{parts[1]}"
