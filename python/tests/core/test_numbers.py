from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from bitpin_sdk._core.numbers import fmt_decimal, to_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1E-8"), "0.00000001"),
        (0.1, "0.1"),
        (1e-7, "0.0000001"),
        (100, "100"),
        (Decimal("1E+3"), "1000"),
        ("63.0", "63"),
        ("0.000", "0"),
        (Decimal("-1.50"), "-1.5"),
        (3145737420, "3145737420"),
    ],
)
def test_fmt_decimal_is_plain(value: object, expected: str) -> None:
    assert fmt_decimal(value) == expected  # type: ignore[arg-type]


def test_to_decimal_from_float_uses_repr() -> None:
    assert to_decimal(0.1) == Decimal("0.1")


def test_to_decimal_none_and_empty() -> None:
    assert to_decimal(None) is None
    assert to_decimal("") is None


def test_to_decimal_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="not a number"):
        to_decimal("abc")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "NaN", "Infinity"])
def test_non_finite_rejected(bad: object) -> None:
    with pytest.raises(ValueError, match="not a finite number"):
        fmt_decimal(bad)  # type: ignore[arg-type]


def test_bool_rejected() -> None:
    with pytest.raises(ValueError, match="not a number"):
        to_decimal(True)


@given(
    st.decimals(
        allow_nan=False, allow_infinity=False, places=12, min_value=-(10**12), max_value=10**12
    )
)
def test_round_trip(d: Decimal) -> None:
    text = fmt_decimal(d)
    assert "E" not in text
    assert "e" not in text
    assert to_decimal(text) == d
