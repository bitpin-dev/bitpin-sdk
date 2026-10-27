"""Exact decimal handling. Amounts and prices never pass through float arithmetic."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

Number = str | int | float | Decimal


def to_decimal(value: Number | None) -> Decimal | None:
    """Parse a server or user value. Floats go through ``repr`` so ``0.1`` stays ``0.1``."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"not a number: {value!r}")
    if isinstance(value, float):
        value = repr(value)
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"not a number: {value!r}") from None


def fmt_decimal(value: Number) -> str:
    """Plain decimal string for the API: no exponent, no trailing zeros.

    ``Decimal("1E-8")`` → ``"0.00000001"``.
    """
    number = to_decimal(value)
    if number is None or not number.is_finite():
        raise ValueError(f"not a finite number: {value!r}")
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text
