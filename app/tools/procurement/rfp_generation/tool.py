import hashlib
from datetime import date
from decimal import Decimal
from html import escape
from uuid import uuid4

from app.clock import MADRID, today
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.documents import get_artifact_store, get_invoice_renderer
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.procurement.rfp_generation.schemas import (
    DocumentFormat,
    RfpInput,
    RfpOutput,
)


def _clean(value: str) -> str:
    return "".join(char for char in value if char.isprintable() or char in "\n\t")


def _cell(value: str) -> str:
    return _clean(value).replace("|", "\\|").replace("\n", " ")


def _plain(value: Decimal) -> str:
    return format(value, "f")


def _markdown(params: RfpInput) -> str:
    requirements = "\n".join(f"- {_clean(value)}" for value in params.requirements)
    criteria = "\n".join(
        f"| {_cell(item.name)} | {_plain(item.weight_pct)} |" for item in params.evaluation_criteria
    )
    suppliers = (
        "\n".join(
            f"- {_clean(item.name)}" + (f" ({_clean(str(item.email))})" if item.email else "")
            for item in params.suppliers
        )
        if params.suppliers
        else "No se han especificado destinatarios previstos."
    )
    budget = _plain(params.budget_max) if params.budget_max is not None else "No se especifica"
    return (
        f"# Solicitud de ofertas: {_clean(params.title)}\n\n"
        "## Objeto\n\n"
        f"{_clean(params.title)}\n\n"
        "## Alcance\n\n"
        f"{_clean(params.scope_description)}\n\n"
        "## Requisitos\n\n"
        f"{requirements}\n\n"
        "## Criterios de evaluación\n\n"
        "| Criterio | Peso (%) |\n|---|---|\n"
        f"{criteria}\n\n"
        "## Calendario\n\n"
        f"Fecha límite de presentación: {params.deadline.isoformat()}\n\n"
        "## Presupuesto máximo\n\n"
        f"{budget}\n\n"
        "## Datos de contacto\n\n"
        f"{_clean(str(params.contact_email))}\n\n"
        "## Destinatarios previstos\n\n"
        f"{suppliers}\n\n"
        "Documento generado automáticamente; no constituye asesoramiento legal.\n"
    )


def _html(params: RfpInput) -> str:
    requirements = "".join(f"<li>{escape(_clean(value))}</li>" for value in params.requirements)
    criteria = "".join(
        f"<tr><td>{escape(_cell(item.name))}</td><td>{_plain(item.weight_pct)}</td></tr>"
        for item in params.evaluation_criteria
    )
    suppliers = (
        "".join(f"<li>{escape(_clean(item.name))}</li>" for item in params.suppliers)
        or "<li>No se han especificado destinatarios previstos.</li>"
    )
    budget = _plain(params.budget_max) if params.budget_max is not None else "No se especifica"
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f"<title>{escape(_clean(params.title))}</title></head><body>"
        f"<h1>Solicitud de ofertas: {escape(_clean(params.title))}</h1>"
        f"<h2>Objeto</h2><p>{escape(_clean(params.title))}</p>"
        f"<h2>Alcance</h2><p>{escape(_clean(params.scope_description))}</p>"
        f"<h2>Requisitos</h2><ul>{requirements}</ul>"
        "<h2>Criterios de evaluación</h2>"
        f"<table><tr><th>Criterio</th><th>Peso (%)</th></tr>{criteria}</table>"
        f"<h2>Calendario</h2><p>Fecha límite: {params.deadline.isoformat()}</p>"
        f"<h2>Presupuesto máximo</h2><p>{budget}</p>"
        f"<h2>Datos de contacto</h2><p>{escape(str(params.contact_email))}</p>"
        f"<h2>Destinatarios previstos</h2><ul>{suppliers}</ul>"
        "<p>Documento generado automáticamente; no constituye asesoramiento legal.</p>"
        "</body></html>"
    )


@tool(
    name="procurement.rfp_generation",
    version="0.1.0",
    title="Generar pliego de solicitud de ofertas",
    permissions=["procurement.write"],
    data_classification="business",
    read_only=False,
    idempotent=True,
    requires_confirmation=True,
    mcp_description=(
        "Genera un pliego editable en Markdown o PDF a partir de requisitos y "
        "criterios de evaluación, lo guarda en el almacén del tenant y registra "
        "su hash. Exige confirmación humana e idempotency_key; no envía nada a "
        "los proveedores ni constituye asesoramiento legal."
    ),
)
async def rfp_generation(params: RfpInput, ctx: ToolContext) -> ToolResult[RfpOutput]:
    if not ctx.confirmed:
        raise ToolError(
            ErrorCode.CONFIRMATION_REQUIRED,
            "procurement.rfp_generation requiere confirmación humana.",
        )
    deadline: date = params.deadline
    if deadline <= today(MADRID):
        raise ToolError(
            ErrorCode.INVALID_PARAMS,
            "deadline debe ser una fecha futura.",
            details={"deadline": deadline.isoformat()},
        )

    document_id = uuid4()
    if params.document_format is DocumentFormat.pdf:
        content = get_invoice_renderer(ctx).render_pdf(_html(params))
    else:
        content = _markdown(params).encode("utf-8")

    path = await get_artifact_store(ctx).save_artifact(
        company_id=ctx.company_id or "",
        document_id=document_id,
        document_type="rfp",
        extension=params.document_format.value,
        content=content,
        index_key=params.idempotency_key,
    )
    checksum = hashlib.sha256(content).hexdigest()
    output = RfpOutput(
        document_id=str(document_id),
        path=path,
        title=params.title,
        deadline=deadline,
        criteria_count=len(params.evaluation_criteria),
        suppliers_count=len(params.suppliers),
        format=params.document_format,
        checksum_sha256=checksum,
        deduplicated=False,
    )
    return tool_result(
        output,
        metadata_extra={
            "source": "document_generator",
            "source_type": "internal",
            "result_type": "mutation",
            "is_estimated": False,
            "idempotency_key": params.idempotency_key,
            "effect": "document_created",
            "document_hash_sha256": checksum,
            "legal_disclaimer_required": True,
        },
        summary=f"Pliego '{params.title}' generado en {params.document_format.value}.",
    )
