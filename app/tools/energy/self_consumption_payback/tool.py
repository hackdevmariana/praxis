from decimal import Decimal, localcontext

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.energy.self_consumption_payback.schemas import (
    CashflowYear,
    SelfConsumptionInput,
    SelfConsumptionOutput,
)


def _irr_pct(capex: Decimal, savings: list[Decimal]) -> Decimal | None:
    if capex <= 0 or max(savings) <= 0 or sum(savings) <= capex:
        return None

    def npv(rate: Decimal) -> Decimal:
        return -capex + sum(
            (item / (Decimal("1") + rate) ** year for year, item in enumerate(savings, 1)),
            Decimal("0"),
        )

    low = Decimal("0")
    high = Decimal("1")
    while npv(high) > 0:
        high *= 2
    for _ in range(120):
        middle = (low + high) / 2
        if npv(middle) > 0:
            low = middle
        else:
            high = middle
    return quantize_money((low + high) / 2 * Decimal("100"))


@tool(
    name="energy.self_consumption_payback",
    version="0.1.0",
    title="Calcular rentabilidad de autoconsumo",
    permissions=["energy.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Simula el ahorro, el payback, el VAN y la TIR de una instalación fotovoltaica "
        "de autoconsumo con degradación anual, excedentes y costes de operación."
    ),
)
async def calculate_self_consumption_payback(
    params: SelfConsumptionInput, ctx: ToolContext
) -> ToolResult[SelfConsumptionOutput]:
    with localcontext() as context:
        context.prec = 40
        degradation = Decimal("1") - params.degradation_pct / Decimal("100")
        self_consumption = params.self_consumption_pct / Decimal("100")
        cashflows: list[CashflowYear] = []
        cumulative = Decimal("0")
        for year in range(1, params.years + 1):
            production = quantize_money(params.annual_production_kwh * degradation ** (year - 1))
            self_consumed = quantize_money(production * self_consumption)
            exported = quantize_money(production - self_consumed)
            savings = quantize_money(
                self_consumed * params.electricity_price_eur_kwh
                + exported * params.export_price_eur_kwh
                - params.annual_opex
            )
            cumulative = quantize_money(cumulative + savings)
            cashflows.append(
                CashflowYear(
                    year=year,
                    production_kwh=production,
                    self_consumed_kwh=self_consumed,
                    exported_kwh=exported,
                    savings=savings,
                    cumulative_savings=cumulative,
                )
            )

        savings_by_year = [item.savings for item in cashflows]
        year1_savings = savings_by_year[0]
        simple_payback = quantize_money(params.capex / year1_savings) if year1_savings > 0 else None

        payback: Decimal | None = None
        if params.capex == 0:
            payback = Decimal("0.00")
        else:
            previous_cumulative = Decimal("0")
            for year, item in enumerate(cashflows, start=1):
                if item.savings > 0 and item.cumulative_savings >= params.capex:
                    payback = quantize_money(
                        Decimal(year - 1) + (params.capex - previous_cumulative) / item.savings
                    )
                    break
                previous_cumulative = item.cumulative_savings

        discount = Decimal("1") + params.discount_rate_pct / Decimal("100")
        npv = quantize_money(
            -params.capex
            + sum(
                (item / discount**year for year, item in enumerate(savings_by_year, 1)),
                Decimal("0"),
            )
        )

    return tool_result(
        SelfConsumptionOutput(
            year1_savings=year1_savings,
            simple_payback_years=simple_payback,
            payback_years=payback,
            npv=npv,
            irr_pct=_irr_pct(params.capex, savings_by_year),
            cashflows=cashflows,
            currency=params.currency,
        ),
        metadata_extra={
            "source": "deterministic",
            "source_type": "deterministic",
            "result_type": "simulation",
            "is_estimated": True,
            "confidence": 0.75,
            "currency": params.currency,
            "unit": "EUR",
            "legal_disclaimer_required": True,
        },
        summary=(
            f"Ahorro de {year1_savings} EUR el primer año; payback "
            f"{payback if payback is not None else 'no alcanzado'} años."
        ),
    )
