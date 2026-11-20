from decimal import Decimal

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.energy.tariff_simulator.schemas import (
    TariffResult,
    TariffSimulatorInput,
    TariffSimulatorOutput,
)


@tool(
    name="energy.tariff_simulator",
    version="0.1.0",
    title="Simular tarifas eléctricas",
    permissions=["energy.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Compara el coste anual de 2 a 5 tarifas eléctricas aportadas por el usuario con un "
        "mismo perfil de consumo, antes de impuestos y sin excedentes de autoconsumo."
    ),
)
async def simulate_tariffs(
    params: TariffSimulatorInput, ctx: ToolContext
) -> ToolResult[TariffSimulatorOutput]:
    annual_consumption = quantize_money(params.annual_consumption_kwh)
    peak_kwh = quantize_money(annual_consumption * params.peak_share_pct / Decimal("100"))
    valley_kwh = quantize_money(annual_consumption - peak_kwh)

    results: list[TariffResult] = []
    for tariff in params.tariffs:
        power_cost = quantize_money(tariff.power_price_eur_kw_year * params.contracted_power_kw)
        energy_cost = quantize_money(
            peak_kwh * tariff.energy_price_peak_eur_kwh
            + valley_kwh * tariff.energy_price_valley_eur_kwh
        )
        standing_cost = quantize_money(tariff.standing_charge_eur_month * Decimal("12"))
        annual_cost = quantize_money(power_cost + energy_cost + standing_cost)
        results.append(
            TariffResult(
                name=tariff.name,
                peak_kwh=peak_kwh,
                valley_kwh=valley_kwh,
                power_cost=power_cost,
                energy_cost=energy_cost,
                standing_cost=standing_cost,
                annual_cost=annual_cost,
                monthly_avg=quantize_money(annual_cost / Decimal("12")),
                rank=0,
                savings_vs_most_expensive=Decimal("0.00"),
                is_cheapest=False,
            )
        )

    results.sort(key=lambda item: (item.annual_cost, item.name))
    most_expensive = max(item.annual_cost for item in results)
    cheapest = results[0].annual_cost
    savings_pct = (
        quantize_money((most_expensive - cheapest) / most_expensive * Decimal("100"))
        if most_expensive > 0
        else None
    )
    for rank, item in enumerate(results, start=1):
        item.rank = rank
        item.is_cheapest = rank == 1
        item.savings_vs_most_expensive = quantize_money(most_expensive - item.annual_cost)

    return tool_result(
        TariffSimulatorOutput(
            annual_consumption_kwh=annual_consumption,
            peak_kwh=peak_kwh,
            valley_kwh=valley_kwh,
            currency="EUR",
            ranking=results,
            savings_pct_best=savings_pct,
        ),
        metadata_extra={
            "source": "user_input",
            "source_type": "user_input",
            "result_type": "comparison",
            "is_estimated": True,
            "confidence": 0.8,
            "currency": "EUR",
            "unit": "EUR/year",
            "legal_disclaimer_required": True,
        },
        summary=(
            f"{len(results)} tarifas comparadas; la mejor cuesta {cheapest} EUR/año "
            "antes de impuestos."
        ),
    )
