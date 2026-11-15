from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, cast

import pint

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.units.convert.schemas import UnitsConvertInput, UnitsConvertOutput

_UREG = pint.UnitRegistry()


def _quantized(value: Decimal, precision: int) -> Decimal:
    quantum = Decimal(1).scaleb(-precision)
    with localcontext() as context:
        context.prec = 50
        return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _factor_decimal(factor: float) -> Decimal:
    with localcontext() as context:
        context.prec = 15
        context.rounding = ROUND_HALF_UP
        rounded = +Decimal(str(factor))
    return Decimal(format(rounded.normalize(), "f"))


def _quantity(value: float, unit: str) -> Any:
    return _UREG.Quantity(value, unit)


def _to(quantity: Any, unit: str) -> Any:
    return quantity.to(unit)


def _magnitude(quantity: Any) -> float:
    return cast("float", quantity.magnitude)


def _units(quantity: Any) -> str:
    return str(quantity.units)


def _dimensionality(quantity: Any) -> str:
    return str(quantity.dimensionality)


@tool(
    name="units.convert",
    version="1.0.0",
    title="Convertir unidades",
    permissions=["units.convert"],
    data_classification="public",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Convierte un valor entre unidades compatibles de longitud, masa, volumen, "
        "superficie, energía o temperatura. Acepta símbolos y nombres de pint; "
        "`gal` es el galón US (para el imperial usar `imperial_gallon`). "
        "No usar para monedas ni para diferencias de temperatura."
    ),
)
async def convert(params: UnitsConvertInput, ctx: ToolContext) -> ToolResult[UnitsConvertOutput]:
    try:
        quantity = _quantity(float(params.value), params.from_unit)
        target = _quantity(1.0, params.to_unit)
    except pint.errors.UndefinedUnitError as error:
        raise ToolError(
            ErrorCode.INVALID_PARAMS,
            f"Unidad desconocida: {error}",
        ) from error

    source_dimension = _dimensionality(quantity)
    target_dimension = _dimensionality(target)
    if source_dimension != target_dimension:
        raise ToolError(
            "incompatible_units",
            f"No se puede convertir {source_dimension} a {target_dimension}",
        )

    try:
        converted = _to(quantity, params.to_unit)
    except pint.errors.DimensionalityError as error:
        raise ToolError("incompatible_units", str(error)) from error

    one = _magnitude(_to(_quantity(1.0, params.from_unit), params.to_unit))
    zero = _magnitude(_to(_quantity(0.0, params.from_unit), params.to_unit))
    factor = _factor_decimal(one - zero)
    value = _quantized(Decimal(str(_magnitude(converted))), params.precision)

    return tool_result(
        UnitsConvertOutput(
            value=value,
            from_unit=_units(quantity),
            to_unit=_units(converted),
            dimension=source_dimension,
            factor=factor,
        )
    )
