import asyncio
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.clock import MADRID, today
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.execution import execute_tool
from app.providers.documents import set_artifact_store, set_document_adapters
from app.registry import registry
from app.result import ToolResult
from app.tools.procurement.rfp_generation.schemas import RfpInput, RfpOutput
from app.tools.procurement.rfp_generation.tool import rfp_generation

CTX = ToolContext(
    request_id="test",
    company_id="33333333-3333-4333-8333-333333333333",
    confirmed=True,
    scopes=frozenset({"procurement.write"}),
)
FUTURE = (today(MADRID) + timedelta(days=30)).isoformat()


def payload(**overrides: object) -> dict[str, Any]:
    value: dict[str, Any] = {
        "title": "Suministro de aceite 2027",
        "category": "supplies",
        "scope_description": (
            "Acuerdo marco anual para el suministro de aceite de oliva virgen extra."
        ),
        "requirements": [
            "Capacidad de suministro mínima de 5.000 litros anuales",
            "Certificación de calidad vigente",
        ],
        "evaluation_criteria": [
            {"name": "Precio", "weight_pct": "30"},
            {"name": "Calidad", "weight_pct": "25"},
            {"name": "Plazo de entrega", "weight_pct": "20"},
            {"name": "Servicio", "weight_pct": "15"},
            {"name": "Sostenibilidad", "weight_pct": "10"},
        ],
        "deadline": FUTURE,
        "budget_max": "25000",
        "contact_email": "compras@asociacion.example",
        "suppliers": [
            {"name": "Aceites S.L.", "email": "ventas@aceites.example"},
            {"name": "Campo Verde S.L.", "email": None},
        ],
        "document_format": "md",
        "idempotency_key": "rfp-aceite-2027",
    }
    value.update(overrides)
    return value


class FakeArtifactStore:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def save_artifact(
        self,
        *,
        company_id: str,
        document_id: UUID,
        document_type: str,
        extension: str,
        content: bytes,
        index_key: str,
    ) -> str:
        self.saved.append(
            {
                "company_id": company_id,
                "document_id": document_id,
                "document_type": document_type,
                "extension": extension,
                "content": content,
                "index_key": index_key,
            }
        )
        return f"{company_id}/{document_id}.{extension}"


class FakeRenderer:
    def __init__(self) -> None:
        self.html: list[str] = []

    def render_pdf(self, html: str) -> bytes:
        self.html.append(html)
        return b"%PDF-1.4 fake"


def install() -> tuple[FakeArtifactStore, FakeRenderer]:
    store = FakeArtifactStore()
    renderer = FakeRenderer()
    set_artifact_store(store)
    set_document_adapters(renderer=renderer)
    return store, renderer


def run_result(**kwargs: object) -> ToolResult[RfpOutput]:
    return asyncio.run(rfp_generation(RfpInput.model_validate(payload(**kwargs)), CTX))


def run_envelope(**kwargs: object) -> dict[str, Any]:
    spec = registry.get("procurement.rfp_generation")
    return asyncio.run(execute_tool(spec, RfpInput.model_validate(payload(**kwargs)), CTX))


def test_markdown_golden_case() -> None:
    store, _ = install()
    result = run_result()
    output = result.data
    saved = store.saved[0]
    markdown = saved["content"].decode("utf-8")

    assert UUID(output.document_id) == saved["document_id"]
    assert output.path == f"{CTX.company_id}/{output.document_id}.md"
    assert output.title == "Suministro de aceite 2027"
    assert output.deadline.isoformat() == FUTURE
    assert output.criteria_count == 5
    assert output.suppliers_count == 2
    assert output.format.value == "md"
    assert output.deduplicated is False
    assert output.checksum_sha256 == sha256(saved["content"]).hexdigest()
    assert saved["document_type"] == "rfp"
    assert saved["index_key"] == "rfp-aceite-2027"
    for section in (
        "## Objeto",
        "## Alcance",
        "## Requisitos",
        "## Criterios de evaluación",
        "| Precio | 30 |",
        "## Calendario",
        "## Presupuesto máximo",
        "25000",
        "## Datos de contacto",
        "compras@asociacion.example",
        "## Destinatarios previstos",
        "Aceites S.L. (ventas@aceites.example)",
        "no constituye asesoramiento legal",
    ):
        assert section in markdown
    assert result.metadata_extra["source"] == "document_generator"
    assert result.metadata_extra["result_type"] == "mutation"
    assert result.metadata_extra["effect"] == "document_created"
    assert result.metadata_extra["legal_disclaimer_required"] is True
    assert result.warnings == []


def test_pdf_uses_renderer_and_returns_pdf_bytes() -> None:
    store, renderer = install()
    output = run_result(document_format="pdf", suppliers=[]).data

    assert output.format.value == "pdf"
    assert output.path.endswith(".pdf")
    assert store.saved[0]["content"] == b"%PDF-1.4 fake"
    assert output.checksum_sha256 == sha256(b"%PDF-1.4 fake").hexdigest()
    assert "<h2>Criterios de evaluación</h2>" in renderer.html[0]
    assert "No se han especificado destinatarios previstos." in renderer.html[0]
    assert "25000" in renderer.html[0]


def test_optional_sections_and_sanitization() -> None:
    store, renderer = install()
    output = run_result(
        budget_max=None,
        title="Aceite\x00 2027",
        evaluation_criteria=[{"name": "Precio | total", "weight_pct": "100"}],
    ).data
    markdown = store.saved[0]["content"].decode("utf-8")

    assert "No se especifica" in markdown
    assert "\\|" in markdown
    assert "\x00" not in markdown
    assert output.criteria_count == 1

    run_result(document_format="pdf", budget_max=None, suppliers=[])
    assert "No se especifica" in renderer.html[-1]


def test_confirmation_is_required() -> None:
    install()
    unconfirmed = replace(CTX, confirmed=False)

    with pytest.raises(ToolError) as excinfo:
        asyncio.run(rfp_generation(RfpInput.model_validate(payload()), unconfirmed))

    assert excinfo.value.code == ErrorCode.CONFIRMATION_REQUIRED


def test_past_deadline_is_rejected() -> None:
    install()
    yesterday = (today(MADRID) - timedelta(days=1)).isoformat()

    with pytest.raises(ToolError) as excinfo:
        run_result(deadline=yesterday)

    assert excinfo.value.code == ErrorCode.INVALID_PARAMS


def test_executor_deduplicates_same_idempotency_key() -> None:
    store, _ = install()
    first = run_envelope()
    second = run_envelope()

    assert first["data"]["deduplicated"] is False
    assert second["data"]["deduplicated"] is True
    assert second["data"]["document_id"] == first["data"]["document_id"]
    assert len(store.saved) == 1


def test_unconfigured_store_fails_closed() -> None:
    with pytest.raises(ToolError) as excinfo:
        run_result()

    assert excinfo.value.code == ErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "evaluation_criteria": [
                {"name": "Precio", "weight_pct": "60"},
                {"name": "Calidad", "weight_pct": "35"},
            ]
        },
        {
            "evaluation_criteria": [
                {"name": "Precio", "weight_pct": "50"},
                {"name": "Precio", "weight_pct": "50"},
            ]
        },
        {"requirements": []},
        {"contact_email": "no-es-un-email"},
        {"budget_max": "-1"},
        {"idempotency_key": "corta"},
    ],
)
def test_invalid_params_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RfpInput.model_validate(payload(**overrides))
