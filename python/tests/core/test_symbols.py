from __future__ import annotations

import pytest

from bitpin_sdk._core.symbols import to_market_id, to_symbol
from bitpin_sdk.errors import BadSymbol


@pytest.mark.parametrize("symbol", ["BTC/IRT", "btc/irt", "BTC_IRT", "btc_irt", " BTC/IRT "])
def test_to_market_id_normalizes(symbol: str) -> None:
    assert to_market_id(symbol) == "BTC_IRT"


def test_to_market_id_keeps_digits() -> None:
    assert to_market_id("1INCH/USDT") == "1INCH_USDT"


@pytest.mark.parametrize("bad", ["BTCIRT", "BTC-IRT", "BTC/", "/IRT", "BTC/IRT/X", "", "BTC_I RT"])
def test_to_market_id_rejects(bad: str) -> None:
    with pytest.raises(BadSymbol):
        to_market_id(bad)


def test_to_symbol() -> None:
    assert to_symbol("BTC_IRT") == "BTC/IRT"


def test_to_symbol_rejects() -> None:
    with pytest.raises(BadSymbol):
        to_symbol("BTCIRT")
