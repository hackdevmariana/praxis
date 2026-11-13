"""Decimal helpers for monetary values."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    """Round a monetary amount to two decimals using ROUND_HALF_UP."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def money_str(value: Decimal) -> str:
    """Serialize a monetary amount as a fixed two-decimal string."""
    return str(quantize_money(value))


def decimal_str(value: Decimal) -> str:
    """Serialize a Decimal preserving its current scale."""
    return str(value)
