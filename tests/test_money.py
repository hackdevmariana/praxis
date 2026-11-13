from decimal import Decimal

from app.money import decimal_str, money_str, quantize_money


def test_quantize_money_rounds_half_up() -> None:
    assert quantize_money(Decimal("2.675")) == Decimal("2.68")
    assert quantize_money(Decimal("-2.675")) == Decimal("-2.68")


def test_money_str_keeps_two_decimals() -> None:
    assert money_str(Decimal("1000")) == "1000.00"
    assert money_str(Decimal("1210.5")) == "1210.50"


def test_decimal_str_preserves_scale() -> None:
    assert decimal_str(Decimal("0.25000")) == "0.25000"
