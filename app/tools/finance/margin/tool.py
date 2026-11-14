from decimal import Decimal

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.margin.schemas import MarginInput, MarginOutput


@tool(
    name="finance.margin",
    version="1.0.0",
    title="Calcular margen y markup",
    permissions=["finance.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Calcula margen comercial y markup a partir de dos de {coste, precio, margen}. "
        "El margen se calcula sobre el precio de venta y el markup sobre el coste. "
        "No usar para calcular impuestos ni descuentos."
    ),
)
async def calculate_margin(params: MarginInput, ctx: ToolContext) -> ToolResult[MarginOutput]:
    warnings: list[str] = []
    cost = params.cost
    price = params.price
    given_margin = params.margin_pct

    if cost is not None and price is not None:
        cost = quantize_money(cost)
        price = quantize_money(price)
    elif cost is not None and given_margin is not None:
        cost = quantize_money(cost)
        price = quantize_money(cost / (1 - given_margin / 100))
    elif price is not None and given_margin is not None:
        price = quantize_money(price)
        cost = quantize_money(price * (1 - given_margin / 100))

    assert cost is not None
    assert price is not None
    margin_amount = quantize_money(price - cost)

    if given_margin is not None:
        margin_pct = quantize_money(given_margin)
    elif price == 0:
        if cost == 0:
            margin_pct = Decimal("0.00")
        else:
            margin_pct = None
            warnings.append("margin_undefined")
    else:
        margin_pct = quantize_money(margin_amount / price * 100)

    if cost == 0:
        if price == 0:
            markup_pct = Decimal("0.00")
        else:
            markup_pct = None
            warnings.append("markup_undefined")
    else:
        markup_pct = quantize_money(margin_amount / cost * 100)

    return tool_result(
        MarginOutput(
            cost=cost,
            price=price,
            margin_amount=margin_amount,
            margin_pct=margin_pct,
            markup_pct=markup_pct,
            currency=params.currency,
        ),
        warnings=warnings,
    )
