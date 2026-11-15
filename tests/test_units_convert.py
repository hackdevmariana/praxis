import asyncio
from decimal import Decimal

import pytest

from app.context import ToolContext
from app.errors import ToolError
from app.tools.units.convert.schemas import UnitsConvertInput, UnitsConvertOutput
from app.tools.units.convert.tool import convert

CTX = ToolContext(request_id="test")


def run(
    value: str,
    from_unit: str,
    to_unit: str,
    precision: int = 6,
) -> UnitsConvertOutput:
    result = asyncio.run(
        convert(
            UnitsConvertInput(
                value=Decimal(value),
                from_unit=from_unit,
                to_unit=to_unit,
                precision=precision,
            ),
            CTX,
        )
    )
    return result.data


def test_length_golden() -> None:
    output = run("10", "km", "mile")

    assert str(output.value) == "6.213712"
    assert output.from_unit == "kilometer"
    assert output.to_unit == "mile"
    assert output.dimension == "[length]"
    assert str(output.factor) == "0.621371192237334"


def test_temperature_golden() -> None:
    freezing = run("0", "°C", "°F", precision=2)
    boiling = run("100", "°C", "°F", precision=2)
    negative = run("-5", "°C", "°F", precision=2)

    assert str(freezing.value) == "32.00"
    assert str(boiling.value) == "212.00"
    assert str(negative.value) == "23.00"
    assert freezing.from_unit == "degree_Celsius"
    assert freezing.to_unit == "degree_Fahrenheit"
    assert str(freezing.factor) == "1.8"
    assert freezing.dimension == "[temperature]"


def test_energy_golden() -> None:
    output = run("1", "kWh", "MJ")

    assert str(output.value) == "3.600000"
    assert str(output.factor) == "3.6"
    assert output.from_unit == "kilowatt_hour"
    assert output.to_unit == "megajoule"


@pytest.mark.parametrize(
    ("value", "from_unit", "to_unit", "expected"),
    [
        ("1", "mile", "km", "1.609344"),
        ("2", "kg", "lb", "4.409245"),
        ("1", "L", "gal", "0.264172"),
        ("100", "m²", "ft²", "1076.391042"),
        ("0", "km", "m", "0.000000"),
        ("1.234", "km", "m", "1234.000000"),
    ],
)
def test_conversion_matrix(value: str, from_unit: str, to_unit: str, expected: str) -> None:
    assert str(run(value, from_unit, to_unit).value) == expected


def test_precision_zero() -> None:
    assert str(run("1.234", "km", "m", precision=0).value) == "1234"


def test_precision_twelve() -> None:
    assert str(run("1", "in", "m", precision=12).value) == "0.025400000000"


def test_energy_dimension_is_expressed_in_base_dimensions() -> None:
    output = run("1", "kWh", "MJ")

    assert output.dimension == "[mass] * [length] ** 2 / [time] ** 2"
    assert output.value == Decimal("3.600000")


def test_monetary_unit_is_invalid_params() -> None:
    with pytest.raises(ToolError) as error:
        run("1", "USD", "EUR")

    assert error.value.code == "invalid_params"


def test_incompatible_units_raise_domain_error() -> None:
    with pytest.raises(ToolError) as error:
        run("1", "kg", "km")

    assert error.value.code == "incompatible_units"
    assert "[mass]" in error.value.message
    assert "[length]" in error.value.message


def test_unknown_unit_is_invalid_params() -> None:
    with pytest.raises(ToolError) as error:
        run("1", "foo", "m")

    assert error.value.code == "invalid_params"
