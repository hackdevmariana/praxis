import hashlib
from datetime import date as Date
from datetime import timedelta
from decimal import Decimal
from html import escape
from uuid import uuid4

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.money import quantize_money
from app.providers.documents import get_document_store, get_invoice_renderer
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.documents.generate_invoice.schemas import (
    GenerateInvoiceInput,
    GenerateInvoiceOutput,
    InvoiceDocumentType,
    LineInput,
)
from app.tools.validate.spanish_id.schemas import SpanishIdInput
from app.tools.validate.spanish_id.tool import spanish_id


def _plain(value: Decimal) -> str:
    return format(value, "f")


def _html(
    params: GenerateInvoiceInput,
    lines: list[tuple[LineInput, Decimal, Decimal]],
    *,
    number: str,
    due_date: Date,
    base: Decimal,
    vat: Decimal,
    total: Decimal,
) -> str:
    client = params.client
    rows = "".join(
        (
            "<tr>"
            f"<td>{escape(line.description)}</td>"
            f"<td>{_plain(line.quantity)}</td>"
            f"<td>{_plain(line.unit_price)}</td>"
            f"<td>{_plain(line.discount_pct)}%</td>"
            f"<td>{_plain(rate)}%</td>"
            f"<td>{_plain(line_total)}</td>"
            "</tr>"
        )
        for line, line_total, rate in lines
    )
    title = (
        "FACTURA"
        if params.document_type is InvoiceDocumentType.invoice
        else "ALBARÁN (documento no fiscal)"
    )
    notes = f"<p><strong>Notas:</strong> {escape(params.notes)}</p>" if params.notes else ""
    terms = (
        f"<p><strong>Condiciones:</strong> {escape(params.payment_terms)}</p>"
        if params.payment_terms
        else ""
    )
    return f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>{title} {escape(number)}</title></head>
<body>
<h1>{title}</h1>
<p><strong>Número:</strong> {escape(number)}</p>
<p><strong>Fecha:</strong> {params.date.isoformat()}</p>
<p><strong>Vencimiento:</strong> {due_date.isoformat()}</p>
<h2>Cliente</h2>
<p>{escape(client.name)}<br>{escape(client.address or "")}<br>
{escape(client.postal_code or "")} {escape(client.municipality or "")}
{escape(client.province or "")} {escape(client.country)}</p>
<table>
<thead><tr><th>Descripción</th><th>Cantidad</th><th>Precio</th><th>Dto.</th><th>IVA</th><th>Importe</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<p><strong>Base:</strong> {_plain(base)} {escape(params.currency)}</p>
<p><strong>IVA:</strong> {_plain(vat)} {escape(params.currency)}</p>
<p><strong>Total:</strong> {_plain(total)} {escape(params.currency)}</p>
{notes}
{terms}
</body>
</html>"""


@tool(
    name="documents.generate_invoice",
    version="1.0.0",
    title="Generar factura o albarán",
    permissions=["documents.write"],
    data_classification="business",
    read_only=False,
    idempotent=True,
    requires_confirmation=True,
    mcp_description=(
        "Calcula una factura o albarán, valida el CIF español del cliente y "
        "genera un PDF mediante un renderizador inyectable. Exige confirmación "
        "humana e idempotency_key. En albaranes el IVA es siempre 0. No envía "
        "el documento por email."
    ),
)
async def generate_invoice(
    params: GenerateInvoiceInput, ctx: ToolContext
) -> ToolResult[GenerateInvoiceOutput]:
    if not ctx.confirmed:
        raise ToolError(
            ErrorCode.CONFIRMATION_REQUIRED,
            "documents.generate_invoice requiere confirmación humana.",
        )

    company_id = ctx.company_id or ""
    if (
        params.document_type is InvoiceDocumentType.invoice
        and params.client.country == "ES"
        and params.client.cif is not None
    ):
        validation = await spanish_id(SpanishIdInput(value=params.client.cif), ctx)
        if not validation.data.valid:
            raise ToolError(
                "invalid_tax_id",
                "El CIF del cliente no es válido.",
                details={"cif": validation.data.normalized},
            )

    lines: list[tuple[LineInput, Decimal, Decimal]] = []
    base = Decimal("0.00")
    groups: dict[Decimal, Decimal] = {}
    for line in params.lines:
        rate = (
            Decimal("0")
            if params.document_type is InvoiceDocumentType.delivery_note
            else line.vat_rate
            if line.vat_rate is not None
            else params.vat_rate
        )
        line_base = quantize_money(line.quantity * line.unit_price * (1 - line.discount_pct / 100))
        base = quantize_money(base + line_base)
        groups[rate] = quantize_money(groups.get(rate, Decimal("0.00")) + line_base)
        lines.append((line, line_base, rate))

    vat = quantize_money(
        sum(
            (quantize_money(group_base * rate / 100) for rate, group_base in groups.items()),
            Decimal("0.00"),
        )
    )
    total = quantize_money(base + vat)
    due_date = params.due_date or params.date + timedelta(days=30)

    store = get_document_store(ctx)
    if params.number is not None:
        number = params.number.upper()
        if await store.number_exists(
            company_id=company_id,
            number=number,
            document_type=params.document_type.value,
        ):
            raise ToolError(
                "conflict",
                "El número de documento ya existe en la empresa.",
                details={"number": number},
            )
    else:
        number = await store.next_number(
            company_id=company_id,
            year=params.date.year,
            series=params.series.upper() if params.series else None,
            document_type=params.document_type.value,
        )

    html = _html(
        params,
        lines,
        number=number,
        due_date=due_date,
        base=base,
        vat=vat,
        total=total,
    )
    pdf = get_invoice_renderer(ctx).render_pdf(html)

    document_id = uuid4()
    invoice_id = uuid4()
    pdf_path = await store.save(
        company_id=company_id,
        document_id=document_id,
        document_type=params.document_type.value,
        number=number,
        issue_date=params.date,
        pdf=pdf,
    )

    output = GenerateInvoiceOutput(
        document_id=str(document_id),
        invoice_id=str(invoice_id),
        pdf_path=pdf_path,
        number=number,
        date=params.date,
        due_date=due_date,
        base=base,
        vat=vat,
        total=total,
        currency=params.currency,
        document_type=params.document_type,
        deduplicated=False,
    )

    return tool_result(
        output,
        metadata_extra={
            "source": "document_generator",
            "source_type": "internal",
            "result_type": "mutation",
            "currency": params.currency,
            "idempotency_key": params.idempotency_key,
            "effect": "created",
            "document_hash_sha256": hashlib.sha256(pdf).hexdigest(),
        },
    )
