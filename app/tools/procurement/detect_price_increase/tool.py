from decimal import Decimal

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.procurement.detect_price_increase.schemas import (
    PriceAlert,
    PriceIncreaseInput,
    PriceIncreaseOutput,
)


@tool(
    name="procurement.detect_price_increase",
    version="0.1.0",
    title="Detectar subidas de precio anómalas",
    permissions=["procurement.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Detecta subidas de precio de compra respecto al precio anterior con un "
        "umbral porcentual configurable, calcula el impacto anual cuando se aporta "
        "la cantidad y clasifica la severidad. No usa modelos estadísticos."
    ),
)
async def detect_price_increase(
    params: PriceIncreaseInput, ctx: ToolContext
) -> ToolResult[PriceIncreaseOutput]:
    alerts: list[PriceAlert] = []
    for item in params.items:
        change_amount = quantize_money(item.current_unit_price - item.previous_unit_price)
        is_new_price = item.previous_unit_price == 0
        change_pct: Decimal | None = None
        if not is_new_price:
            change_pct = quantize_money(change_amount / item.previous_unit_price * 100)

        annual_impact: Decimal | None = None
        if item.annual_quantity is not None:
            annual_impact = quantize_money(change_amount * item.annual_quantity)

        is_anomalous = change_pct is not None and change_pct >= params.threshold_pct
        if change_pct is None:
            severity = "new_price"
        elif change_pct >= params.threshold_pct * 2:
            severity = "high"
        elif is_anomalous:
            severity = "medium"
        else:
            severity = "low"

        alerts.append(
            PriceAlert(
                supplier=item.supplier,
                product_code=item.product_code,
                description=item.description,
                previous_unit_price=quantize_money(item.previous_unit_price),
                current_unit_price=quantize_money(item.current_unit_price),
                change_amount=change_amount,
                change_pct=change_pct,
                annual_impact=annual_impact,
                is_new_price=is_new_price,
                is_anomalous=is_anomalous,
                severity=severity,
            )
        )

    alerts.sort(
        key=lambda alert: (
            alert.change_pct is None,
            -(alert.change_pct or Decimal("0")),
            alert.description,
        )
    )
    high_count = sum(alert.severity == "high" for alert in alerts)
    medium_count = sum(alert.severity == "medium" for alert in alerts)
    new_price_count = sum(alert.severity == "new_price" for alert in alerts)
    output = PriceIncreaseOutput(
        alerts=alerts,
        anomalous_count=sum(alert.is_anomalous for alert in alerts),
        high_count=high_count,
        medium_count=medium_count,
        new_price_count=new_price_count,
        currency="EUR",
    )
    return tool_result(
        output,
        metadata_extra={
            "source": "user_input",
            "source_type": "user_input",
            "result_type": "analysis",
            "is_estimated": True,
            "confidence": 0.9,
            "currency": "EUR",
            "legal_disclaimer_required": False,
        },
        summary=f"{output.anomalous_count} subidas anómalas detectadas.",
    )
