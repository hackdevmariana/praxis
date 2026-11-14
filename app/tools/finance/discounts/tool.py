from decimal import Decimal

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.discounts.schemas import (
    DiscountOperation,
    DiscountsInput,
    DiscountsOutput,
)


@tool(
    name="finance.discounts",
    version="1.0.0",
    title="Aplicar descuentos en cascada",
    permissions=["finance.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Aplica varios descuentos porcentuales en cascada o reconstruye el importe "
        "original desde el final. Los descuentos son secuenciales, no aditivos. "
        "No usar para descuentos por importe fijo."
    ),
)
async def calculate_discounts(
    params: DiscountsInput, ctx: ToolContext
) -> ToolResult[DiscountsOutput]:
    factor = Decimal(1)
    for discount in params.discounts:
        factor *= 1 - discount / 100

    if params.operation is DiscountOperation.apply:
        original = quantize_money(params.amount)
        final = quantize_money(params.amount * factor)
    else:
        if factor == 0:
            raise ToolError(
                ErrorCode.INVALID_PARAMS,
                "No se puede reconstruir el importe original con un descuento del 100%.",
            )
        original = quantize_money(params.amount / factor)
        final = quantize_money(params.amount)

    discount_amount = quantize_money(abs(original - final))
    effective_pct = (
        quantize_money((1 - final / original) * 100) if original != 0 else Decimal("0.00")
    )

    return tool_result(
        DiscountsOutput(
            original_amount=original,
            final_amount=final,
            discount_amount=discount_amount,
            effective_discount_pct=effective_pct,
            currency=params.currency,
        )
    )
