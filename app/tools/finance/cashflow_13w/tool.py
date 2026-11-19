from datetime import timedelta

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.cashflow_13w.schemas import (
    Cashflow13wInput,
    Cashflow13wOutput,
    CashflowWeek,
)


@tool(
    name="finance.cashflow_13w",
    version="0.1.0",
    title="Previsión de tesorería a 13 semanas",
    permissions=["finance.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Proyecta la tesorería semana a semana durante 13 semanas a partir de flujos "
        "semanales aportados. No modela impuestos, financiación nueva ni estacionalidad."
    ),
)
async def cashflow_13w(params: Cashflow13wInput, ctx: ToolContext) -> ToolResult[Cashflow13wOutput]:
    opening_balance = quantize_money(params.opening_balance)
    closing_balance = opening_balance
    weeks: list[CashflowWeek] = []

    for index, (inflow, outflow) in enumerate(
        zip(params.weekly_inflows, params.weekly_outflows, strict=True), start=1
    ):
        inflow = quantize_money(inflow)
        outflow = quantize_money(outflow)
        net = quantize_money(inflow - outflow)
        closing_balance = quantize_money(closing_balance + net)
        week_start = (
            None
            if params.start_date is None
            else params.start_date + timedelta(days=7 * (index - 1))
        )
        weeks.append(
            CashflowWeek(
                week=index,
                week_start=week_start,
                inflow=inflow,
                outflow=outflow,
                net=net,
                closing_balance=closing_balance,
            )
        )

    minimum = min(weeks, key=lambda week: week.closing_balance)
    negative_weeks = sum(week.closing_balance < 0 for week in weeks)
    warnings = ["negative_balance_risk"] if negative_weeks else []

    return tool_result(
        Cashflow13wOutput(
            opening_balance=opening_balance,
            weeks=weeks,
            end_balance=weeks[-1].closing_balance,
            min_balance=minimum.closing_balance,
            min_week=minimum.week,
            weeks_with_negative_balance=negative_weeks,
            currency=params.currency,
        ),
        warnings=warnings,
        metadata_extra={
            "source": "user_input",
            "source_type": "user_input",
            "result_type": "forecast",
            "is_estimated": True,
            "confidence": 0.7,
            "currency": params.currency,
            "legal_disclaimer_required": True,
        },
    )
