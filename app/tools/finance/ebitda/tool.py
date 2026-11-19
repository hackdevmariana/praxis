from decimal import Decimal

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.ebitda.schemas import EbitdaInput, EbitdaOutput


def _pct(value: Decimal, revenue: Decimal) -> Decimal | None:
    if revenue == 0:
        return None
    return quantize_money(value / revenue * 100)


@tool(
    name="finance.ebitda",
    version="0.1.0",
    title="Calcular EBITDA y EBITDA ajustado",
    permissions=["finance.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Calcula EBITDA, EBITDA ajustado y EBIT a partir de ingresos, costes y gastos "
        "operativos aportados por el llamador. No calcula beneficio neto ni es una cifra "
        "auditada."
    ),
)
async def calculate_ebitda(params: EbitdaInput, ctx: ToolContext) -> ToolResult[EbitdaOutput]:
    revenue = quantize_money(params.revenue)
    cogs = quantize_money(params.cogs)
    operating_expenses = quantize_money(params.operating_expenses)
    depreciation_amortization = quantize_money(params.depreciation_amortization)
    non_recurring_income = quantize_money(params.non_recurring_income)
    non_recurring_expenses = quantize_money(params.non_recurring_expenses)

    ebitda = quantize_money(revenue - cogs - operating_expenses)
    adjusted_ebitda = quantize_money(ebitda - non_recurring_income + non_recurring_expenses)
    ebit = quantize_money(ebitda - depreciation_amortization)

    margins = (
        _pct(ebitda, revenue),
        _pct(adjusted_ebitda, revenue),
        _pct(ebit, revenue),
    )
    warnings = ["undefined_ratio"] if any(value is None for value in margins) else []

    return tool_result(
        EbitdaOutput(
            ebitda=ebitda,
            adjusted_ebitda=adjusted_ebitda,
            ebit=ebit,
            ebitda_margin_pct=margins[0],
            adjusted_ebitda_margin_pct=margins[1],
            ebit_margin_pct=margins[2],
            currency=params.currency,
        ),
        warnings=warnings,
        metadata_extra={
            "source": "user_input",
            "source_type": "user_input",
            "result_type": "calculation",
            "is_estimated": True,
            "confidence": 0.8,
            "currency": params.currency,
            "legal_disclaimer_required": True,
        },
    )
