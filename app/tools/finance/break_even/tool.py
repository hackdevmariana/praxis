from decimal import Decimal
from math import ceil

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.break_even.schemas import BreakEvenInput, BreakEvenOutput


@tool(
    name="finance.break_even",
    version="0.1.0",
    title="Calcular punto de equilibrio",
    permissions=["finance.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Calcula el punto de equilibrio unitario, los ingresos necesarios, las unidades "
        "para un objetivo de beneficio y el margen de seguridad. No incluye impuestos ni "
        "costes financieros."
    ),
)
async def calculate_break_even(
    params: BreakEvenInput, ctx: ToolContext
) -> ToolResult[BreakEvenOutput]:
    fixed_costs = quantize_money(params.fixed_costs)
    variable_cost_per_unit = quantize_money(params.variable_cost_per_unit)
    price_per_unit = quantize_money(params.price_per_unit)
    target_profit = quantize_money(params.target_profit)

    contribution_margin_per_unit = quantize_money(price_per_unit - variable_cost_per_unit)
    if contribution_margin_per_unit <= 0:
        raise ToolError(ErrorCode.INVALID_PARAMS, "El margen de contribución debe ser positivo")

    contribution_margin_pct = quantize_money(contribution_margin_per_unit / price_per_unit * 100)
    break_even_units = ceil(fixed_costs / contribution_margin_per_unit)
    break_even_revenue = quantize_money(fixed_costs * price_per_unit / contribution_margin_per_unit)
    units_for_target_profit = ceil((fixed_costs + target_profit) / contribution_margin_per_unit)

    if params.expected_units in (None, 0):
        margin_of_safety_units = None
        margin_of_safety_pct = None
    else:
        margin_of_safety_units = params.expected_units - break_even_units
        margin_of_safety_pct = quantize_money(
            Decimal(margin_of_safety_units) / Decimal(params.expected_units) * 100
        )

    return tool_result(
        BreakEvenOutput(
            contribution_margin_per_unit=contribution_margin_per_unit,
            contribution_margin_pct=contribution_margin_pct,
            break_even_units=break_even_units,
            break_even_revenue=break_even_revenue,
            units_for_target_profit=units_for_target_profit,
            margin_of_safety_units=margin_of_safety_units,
            margin_of_safety_pct=margin_of_safety_pct,
            currency=params.currency,
        ),
        metadata_extra={
            "source": "user_input",
            "source_type": "user_input",
            "result_type": "calculation",
            "is_estimated": True,
            "confidence": 0.85,
            "currency": params.currency,
            "legal_disclaimer_required": True,
        },
    )
