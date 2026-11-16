from decimal import Decimal

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.procurement.tpv_savings.schemas import (
    TpvSavingsInput,
    TpvSavingsOutput,
)


@tool(
    name="procurement.tpv_savings",
    version="1.0.0",
    title="Calcular ahorro por cambio de TPV",
    permissions=["procurement.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Compara el coste anual de comisiones porcentuales de dos TPV y calcula "
        "el ahorro anual, mensual, porcentual y por ticket. Solo considera la "
        "comisión porcentual; no incluye cuotas fijas, alquiler de terminal ni "
        "penalizaciones. Es una estimación, no una oferta vinculante."
    ),
)
async def calculate_tpv_savings(
    params: TpvSavingsInput, ctx: ToolContext
) -> ToolResult[TpvSavingsOutput]:
    current_cost = quantize_money(params.annual_card_turnover * params.current_rate_pct / 100)
    new_cost = quantize_money(params.annual_card_turnover * params.new_rate_pct / 100)
    annual_savings = quantize_money(current_cost - new_cost)
    monthly_savings = quantize_money(annual_savings / Decimal("12"))

    warnings: list[str] = []
    savings_pct: Decimal | None = None
    if current_cost > 0:
        savings_pct = quantize_money(annual_savings / current_cost * 100)
    else:
        warnings.append("undefined_savings_pct")

    savings_per_ticket: Decimal | None = None
    if params.average_ticket is not None and params.annual_card_turnover > 0:
        savings_per_ticket = quantize_money(
            annual_savings * params.average_ticket / params.annual_card_turnover
        )

    return tool_result(
        TpvSavingsOutput(
            current_cost=current_cost,
            new_cost=new_cost,
            annual_savings=annual_savings,
            monthly_savings=monthly_savings,
            savings_pct=savings_pct,
            savings_per_ticket=savings_per_ticket,
            currency=params.currency,
        ),
        warnings=warnings,
        metadata_extra={
            "result_type": "calculation",
            "is_estimated": True,
            "confidence": 0.9,
            "currency": params.currency,
            "legal_disclaimer_required": True,
        },
    )
