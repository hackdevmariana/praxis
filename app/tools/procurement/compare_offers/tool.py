from decimal import Decimal
from typing import Any

from app.context import ToolContext
from app.errors import ToolError
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.procurement.compare_offers.schemas import (
    CompareOffersInput,
    CompareOffersOutput,
    NormalizeBy,
    OfferInput,
    OfferRow,
)

_METRIC_FIELD = {
    NormalizeBy.total_cost: "total_cost",
    NormalizeBy.annual: "annual_cost",
    NormalizeBy.monthly: "monthly_cost",
}


def _net(offer: OfferInput, value: Decimal) -> Decimal:
    if offer.vat_included:
        return quantize_money(value / (1 + offer.vat_rate / 100))
    return quantize_money(value)


def _year_prices(offer: OfferInput, years: int) -> list[Decimal]:
    prices: list[Decimal] = []
    for year in range(1, years + 1):
        if year == 1:
            value = offer.monthly_price
        elif year == 2:
            value = offer.year2_price if offer.year2_price is not None else offer.monthly_price
        else:
            value = (
                offer.year3_price
                if offer.year3_price is not None
                else offer.year2_price
                if offer.year2_price is not None
                else offer.monthly_price
            )
        prices.append(_net(offer, value))
    return prices


@tool(
    name="procurement.compare_offers",
    version="1.0.0",
    title="Comparar ofertas de proveedores",
    permissions=["procurement.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Normaliza de 2 a 5 ofertas de proveedor a un coste total comparable a "
        "varios años, siempre sin IVA. Suma cuotas recurrentes, costes de alta y "
        "penalizaciones de cancelación. Es una estimación basada en precios "
        "aportados, no una recomendación de compra."
    ),
)
async def compare_offers(
    params: CompareOffersInput, ctx: ToolContext
) -> ToolResult[CompareOffersOutput]:
    currencies = {offer.currency for offer in params.offers}
    if len(currencies) > 1:
        raise ToolError(
            "currency_mismatch",
            "Todas las ofertas deben usar la misma divisa.",
            details={"currencies": sorted(currencies)},
        )
    currency = next(iter(currencies))

    warnings: list[str] = []
    if len(params.offers) == 2:
        warnings.append("few_offers")
    if len({offer.vat_included for offer in params.offers}) > 1:
        warnings.append("mixed_vat_basis_normalized")

    rows: list[OfferRow] = []
    for offer in params.offers:
        prices = _year_prices(offer, params.years)
        recurring_cost = quantize_money(Decimal("12") * sum(prices))
        one_off_cost = quantize_money(
            _net(offer, offer.upfront_cost) + _net(offer, offer.cancellation_cost)
        )
        total_cost = quantize_money(recurring_cost + one_off_cost)
        rows.append(
            OfferRow(
                supplier=offer.supplier,
                monthly_price_net=_net(offer, offer.monthly_price),
                recurring_cost=recurring_cost,
                one_off_cost=one_off_cost,
                total_cost=total_cost,
                annual_cost=quantize_money(total_cost / params.years),
                monthly_cost=quantize_money(total_cost / (params.years * Decimal("12"))),
                permanence_months=offer.permanence_months,
                rank=0,
                is_cheapest=False,
                savings_vs_most_expensive=Decimal("0.00"),
            )
        )

    metric_field = _METRIC_FIELD[params.normalize_by]
    rows.sort(key=lambda row: (getattr(row, metric_field), row.supplier))
    most_expensive = max(row.total_cost for row in rows)
    normalized: list[OfferRow] = []
    for index, row in enumerate(rows, start=1):
        normalized.append(
            row.model_copy(
                update={
                    "rank": index,
                    "is_cheapest": index == 1,
                    "savings_vs_most_expensive": quantize_money(most_expensive - row.total_cost),
                }
            )
        )

    ranking: list[dict[str, Any]] = []
    for row in normalized:
        entry: dict[str, Any] = {
            "rank": row.rank,
            "supplier": row.supplier,
            "total_cost": row.total_cost,
        }
        if metric_field != "total_cost":
            entry[metric_field] = getattr(row, metric_field)
        ranking.append(entry)

    return tool_result(
        CompareOffersOutput(
            years=params.years,
            normalize_by=params.normalize_by,
            currency=currency,
            ranking=ranking,
            normalized_table=normalized,
        ),
        warnings=warnings,
        metadata_extra={
            "source": "user_input",
            "source_type": "user_input",
            "result_type": "comparison",
            "is_estimated": True,
            "confidence": 0.85,
            "currency": currency,
            "legal_disclaimer_required": True,
        },
    )
