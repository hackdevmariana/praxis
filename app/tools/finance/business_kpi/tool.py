from decimal import Decimal

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.business_kpi.schemas import BusinessKpiInput, BusinessKpiOutput


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return quantize_money(numerator / denominator * 100)


def _days(balance: Decimal, flow: Decimal, period_days: int) -> Decimal | None:
    if flow == 0:
        return None
    return quantize_money(balance / flow * period_days)


@tool(
    name="finance.business_kpi",
    version="0.1.0",
    title="Calcular KPIs financieros",
    permissions=["finance.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Calcula márgenes, rentabilidad, ciclo de caja y liquidez a partir de un estado "
        "financiero resumido aportado por el llamador. No sustituye a un estado contable "
        "auditado ni incluye impuestos o intereses."
    ),
)
async def calculate_business_kpi(
    params: BusinessKpiInput, ctx: ToolContext
) -> ToolResult[BusinessKpiOutput]:
    revenue = quantize_money(params.revenue)
    cogs = quantize_money(params.cogs)
    operating_expenses = quantize_money(params.operating_expenses)
    depreciation_amortization = quantize_money(params.depreciation_amortization)
    receivables = quantize_money(params.receivables)
    payables = quantize_money(params.payables)
    inventory = quantize_money(params.inventory)
    cash = quantize_money(params.cash)
    current_liabilities = quantize_money(params.current_liabilities)

    gross_profit = quantize_money(revenue - cogs)
    gross_margin_pct = _pct(gross_profit, revenue)
    ebit = quantize_money(gross_profit - operating_expenses)
    ebit_margin_pct = _pct(ebit, revenue)
    ebitda = quantize_money(ebit + depreciation_amortization)
    dso_days = _days(receivables, revenue, params.period_days)
    dpo_days = _days(payables, cogs, params.period_days)
    dio_days = _days(inventory, cogs, params.period_days)

    if dso_days is None or dpo_days is None or dio_days is None:
        cash_conversion_cycle_days = None
    else:
        cash_conversion_cycle_days = quantize_money(dso_days + dio_days - dpo_days)

    current_assets = quantize_money(cash + receivables + inventory)
    current_ratio = (
        None if current_liabilities == 0 else quantize_money(current_assets / current_liabilities)
    )
    working_capital = quantize_money(current_assets - current_liabilities)

    warnings: list[str] = []
    undefined = (
        gross_margin_pct,
        ebit_margin_pct,
        dso_days,
        dpo_days,
        dio_days,
        cash_conversion_cycle_days,
        current_ratio,
    )
    if any(value is None for value in undefined):
        warnings.append("undefined_ratio")

    return tool_result(
        BusinessKpiOutput(
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            ebit=ebit,
            ebit_margin_pct=ebit_margin_pct,
            ebitda=ebitda,
            dso_days=dso_days,
            dpo_days=dpo_days,
            dio_days=dio_days,
            cash_conversion_cycle_days=cash_conversion_cycle_days,
            current_ratio=current_ratio,
            working_capital=working_capital,
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
