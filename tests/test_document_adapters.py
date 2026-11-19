import asyncio
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

import app.providers.document_adapters as adapters
from app.errors import ToolError
from app.providers.documents import StoredDocument, set_document_adapters
from app.tools.documents.extract_invoice.schemas import ExtractInvoiceInput
from app.tools.documents.extract_invoice.tool import extract_invoice
from tests.test_documents_extract_invoice import CTX, DOCUMENT_ID, install_document

COMPANY_ID = "3f1c2a9e-0000-4000-8000-000000000002"


class FakeOcr:
    async def extract_text(self, *, content: bytes, language: str | None) -> str:
        return (
            "FACTURA F-2026-0042\nFECHA 15/01/2026\n"
            "EMISORA PRUEBAS SL CIF B12345678\n"
            "BASE IMPONIBLE 100,00 EUR\nIVA 21,00 EUR\nTOTAL 121,00 EUR\n"
        )


def test_local_document_store_roundtrip(tmp_path: Path) -> None:
    store = adapters.LocalFileDocumentStore(tmp_path)
    document_id = uuid4()

    assert (
        asyncio.run(
            store.next_number(
                company_id=COMPANY_ID,
                year=2026,
                series="F",
                document_type="invoice",
            )
        )
        == "F-2026-0001"
    )
    path = asyncio.run(
        store.save(
            company_id=COMPANY_ID,
            document_id=document_id,
            document_type="invoice",
            number="F-2026-0001",
            issue_date=date(2026, 1, 15),
            pdf=b"%PDF-1.7 fake",
        )
    )

    assert path.endswith(f"{document_id}.pdf")
    assert asyncio.run(
        store.number_exists(company_id=COMPANY_ID, number="F-2026-0001", document_type="invoice")
    )
    repository = adapters.LocalFileDocumentRepository(tmp_path)
    document = asyncio.run(repository.get(company_id=COMPANY_ID, document_id=document_id))

    assert isinstance(document, StoredDocument)
    assert document.content == b"%PDF-1.7 fake"


def test_weasyprint_renderer_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> object:
        raise ImportError("no weasyprint")

    monkeypatch.setattr(adapters.importlib, "import_module", missing)

    with pytest.raises(ToolError) as error:
        adapters.WeasyPrintInvoiceRenderer().render_pdf("<p>factura</p>")

    assert error.value.code == "provider_unavailable"


def test_tesseract_ocr_reports_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_binary(_cmd: str) -> None:
        return None

    monkeypatch.setattr(adapters.shutil, "which", missing_binary)

    with pytest.raises(ToolError) as error:
        asyncio.run(adapters.TesseractInvoiceOcr().extract_text(content=b"%PDF-1.7", language="es"))

    assert error.value.code == "provider_unavailable"


def test_extract_invoice_uses_configured_ocr() -> None:
    install_document("invoice-blank.pdf")
    set_document_adapters(ocr=FakeOcr())

    result = asyncio.run(
        extract_invoice(
            ExtractInvoiceInput.model_validate({"document_id": str(DOCUMENT_ID)}),
            CTX,
        )
    )

    assert result.data.issuer is not None
    assert "PRUEBAS SL" in result.data.issuer
    assert result.metadata_extra["ocr_used"] is True
    assert result.metadata_extra["processor"] == "tesseract"
