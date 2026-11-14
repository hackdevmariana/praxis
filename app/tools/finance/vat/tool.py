from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.vat.schemas import VatInput, VatOperation, VatOutput


@tool(
    name="finance.vat",
    version="1.0.0",
    title="Calcular IVA",
    permissions=["finance.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Suma, extrae o resta IVA de un importe con redondeo al céntimo. "
        "El tipo de IVA lo aporta el llamador; no se infiere del producto. "
        "No usar para IRPF, impuesto de sociedades ni retenciones."
    ),
)
async def calculate_vat(params: VatInput, ctx: ToolContext) -> ToolResult[VatOutput]:
    amount = quantize_money(params.amount)

    if params.operation is VatOperation.add:
        base = amount
        vat = quantize_money(base * params.rate / 100)
        total = quantize_money(base + vat)
    else:
        total = amount
        base = quantize_money(total / (1 + params.rate / 100))
        vat = quantize_money(total - base)

    return tool_result(
        VatOutput(
            base_amount=base,
            vat_rate=params.rate,
            vat_amount=vat,
            total_amount=total,
            currency=params.currency,
        )
    )
