from decimal import ROUND_HALF_UP, Decimal

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.energy.carbon_footprint.schemas import CarbonInput, CarbonOutput, SourceEmission

FACTORS_VERSION = "2026.1"
DEFAULT_FACTORS: dict[str, Decimal] = {
    "electricity": Decimal("0.150"),
    "natural_gas": Decimal("0.202"),
    "diesel": Decimal("2.680"),
    "gasoline": Decimal("2.310"),
    "waste": Decimal("0.500"),
    "transport": Decimal("0.120"),
}


@tool(
    name="energy.carbon_footprint",
    version="0.1.0",
    title="Calcular huella de carbono",
    permissions=["energy.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Calcula emisiones de kgCO2e por alcance a partir de consumos de electricidad, gas, "
        "combustibles, residuos y transporte, con factores versionados de España. "
        "No sustituye un inventario corporativo auditado."
    ),
)
async def calculate_carbon_footprint(
    params: CarbonInput, ctx: ToolContext
) -> ToolResult[CarbonOutput]:
    overrides = params.factor_overrides or {}
    sources = (
        ("electricity", 2, "kWh", params.electricity_kwh),
        ("natural_gas", 1, "kWh", params.gas_kwh),
        ("diesel", 1, "L", params.diesel_liters),
        ("gasoline", 1, "L", params.gasoline_liters),
        ("waste", 3, "kg", params.waste_kg),
        ("transport", 3, "km", params.transport_km),
    )

    by_source: list[SourceEmission] = []
    scope_totals = {1: Decimal("0"), 2: Decimal("0"), 3: Decimal("0")}
    for activity, scope, unit, quantity in sources:
        if quantity == 0:
            continue
        factor = overrides.get(activity, DEFAULT_FACTORS[activity])
        emissions = quantize_money(quantity * factor)
        by_source.append(
            SourceEmission(
                activity=activity,
                scope=scope,
                quantity=quantity,
                unit=unit,
                factor=factor,
                emissions_kgco2e=emissions,
            )
        )
        scope_totals[scope] += emissions

    scope1 = quantize_money(scope_totals[1])
    scope2 = quantize_money(scope_totals[2])
    scope3 = quantize_money(scope_totals[3])
    total = quantize_money(scope1 + scope2 + scope3)
    denominator = params.electricity_kwh + params.gas_kwh
    intensity = (
        (total / denominator).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if denominator > 0
        else None
    )

    warnings: list[str] = []
    if overrides:
        warnings.append("custom_factors")
    if (params.diesel_liters > 0 or params.gasoline_liters > 0) and params.transport_km > 0:
        warnings.append("possible_double_counting")

    return tool_result(
        CarbonOutput(
            period_start=params.period_start,
            period_end=params.period_end,
            scope1_kgco2e=scope1,
            scope2_kgco2e=scope2,
            scope3_kgco2e=scope3,
            total_kgco2e=total,
            intensity_kgco2e_per_kwh=intensity,
            by_source=by_source,
        ),
        warnings=warnings,
        metadata_extra={
            "source": "deterministic",
            "source_type": "deterministic",
            "result_type": "calculation",
            "is_estimated": True,
            "confidence": 0.7,
            "unit": "kgCO2e",
            "factors_version": FACTORS_VERSION,
            "factors_source": "custom" if overrides else "default",
            "legal_disclaimer_required": True,
        },
        summary=f"Huella de carbono: {total} kgCO2e en tres alcances.",
    )
