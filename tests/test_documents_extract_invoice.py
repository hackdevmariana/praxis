import asyncio
from datetime import date as Date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

import app.tools.documents.extract_invoice.tool as extract_tool
from app.context import ToolContext
from app.errors import ToolError
from app.providers.documents import (
    StoredDocument,
    set_document_repository,
)
from app.tools.documents.extract_invoice.schemas import (
    DocumentType,
    ExtractInvoiceInput,
    ExtractInvoiceOutput,
)
from app.tools.documents.extract_invoice.tool import extract_invoice

CTX = ToolContext(request_id="test", company_id="company-1")
DOCUMENT_ID = UUID("3f1c2a9e-0000-4000-8000-000000000001")
FIXTURES = Path(__file__).parent / "fixtures"


class FakeDocumentRepository:
    def __init__(self, documents: dict[UUID, StoredDocument]) -> None:
        self.documents = documents
        self.calls = 0

    async def get(self, *, company_id: str, document_id: UUID) -> StoredDocument | None:
        self.calls += 1
        document = self.documents.get(document_id)
        if document is None or document.company_id != company_id:
            return None
        return document


def install_document(
    filename: str,
    *,
    document_id: UUID = DOCUMENT_ID,
    content: bytes | None = None,
) -> FakeDocumentRepository:
    data = content if content is not None else (FIXTURES / filename).read_bytes()
    repository = FakeDocumentRepository(
        {
            document_id: StoredDocument(
                document_id=document_id,
                company_id="company-1",
                filename=filename,
                content=data,
            )
        }
    )
    set_document_repository(repository)
    return repository


def run_result(**kwargs: object) -> ExtractInvoiceOutput:
    return asyncio.run(extract_invoice(ExtractInvoiceInput.model_validate(kwargs), CTX)).data


def test_digital_invoice_golden() -> None:
    repository = install_document("invoice-F-2026-0042.pdf")

    result = asyncio.run(
        extract_invoice(
            ExtractInvoiceInput.model_validate(
                {
                    "document_id": str(DOCUMENT_ID),
                    "document_type": "invoice",
                }
            ),
            CTX,
        )
    )

    data = result.data
    assert data.issuer == "Suministros García S.L."
    assert data.issuer_cif == "B12345674"
    assert data.number == "F-2026-0042"
    assert data.date == Date(2026, 11, 5)
    assert data.due_date == Date(2026, 12, 5)
    assert len(data.lines) == 2
    assert data.lines[0].description == "Tornillos M8 (caja 100)"
    assert data.lines[0].quantity == Decimal("10")
    assert data.lines[0].unit_price == Decimal("4.50")
    assert data.lines[0].line_total == Decimal("45.00")
    assert data.base == Decimal("165.00")
    assert data.vat == Decimal("34.65")
    assert data.total == Decimal("199.65")
    assert data.currency == "EUR"
    assert data.needs_review is False
    assert data.confidence == 0.93
    assert result.warnings == []
    assert result.metadata_extra["processor"] == "pdfplumber"
    assert result.metadata_extra["language_detected"] == "es"
    assert result.metadata_extra["extraction_cached"] is False
    assert repository.calls == 1


def test_repeated_extraction_uses_cache() -> None:
    repository = install_document("invoice-F-2026-0042.pdf")
    payload = {
        "document_id": str(DOCUMENT_ID),
        "document_type": "invoice",
    }

    asyncio.run(extract_invoice(ExtractInvoiceInput.model_validate(payload), CTX))
    second = asyncio.run(extract_invoice(ExtractInvoiceInput.model_validate(payload), CTX))

    assert second.metadata_extra["extraction_cached"] is True
    assert second.metadata_extra["processing_time_ms"] == 0
    assert repository.calls == 1


def test_document_not_found() -> None:
    set_document_repository(FakeDocumentRepository({}))

    with pytest.raises(ToolError) as error:
        run_result(document_id=str(DOCUMENT_ID))

    assert error.value.code == "document_not_found"


def test_other_tenant_cannot_extract_document() -> None:
    repository = FakeDocumentRepository(
        {
            DOCUMENT_ID: StoredDocument(
                document_id=DOCUMENT_ID,
                company_id="otra",
                filename="invoice.pdf",
                content=(FIXTURES / "invoice-F-2026-0042.pdf").read_bytes(),
            )
        }
    )
    set_document_repository(repository)

    with pytest.raises(ToolError) as error:
        run_result(document_id=str(DOCUMENT_ID))

    assert error.value.code == "document_not_found"


def test_non_pdf_is_unsupported() -> None:
    install_document("invoice-F-2026-0042.pdf", content=b"not a pdf")

    with pytest.raises(ToolError) as error:
        run_result(document_id=str(DOCUMENT_ID))

    assert error.value.code == "unsupported_format"


def test_unreadable_pdf_is_unsupported() -> None:
    install_document("invoice-F-2026-0042.pdf", content=b"%PDF-1.4 broken")

    with pytest.raises(ToolError) as error:
        run_result(document_id=str(DOCUMENT_ID))

    assert error.value.code == "unsupported_format"


def test_document_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    install_document("invoice-F-2026-0042.pdf")
    monkeypatch.setattr(extract_tool, "_MAX_DOCUMENT_SIZE", 10)

    with pytest.raises(ToolError) as error:
        run_result(document_id=str(DOCUMENT_ID))

    assert error.value.code == "document_too_large"


def test_blank_pdf_requests_manual_review() -> None:
    install_document("invoice-blank.pdf")

    result = asyncio.run(
        extract_invoice(
            ExtractInvoiceInput.model_validate({"document_id": str(DOCUMENT_ID)}),
            CTX,
        )
    )

    assert result.data.issuer is None
    assert result.data.total is None
    assert result.data.lines == []
    assert result.data.confidence == 0.0
    assert result.data.needs_review is True
    assert result.warnings == [
        "low_confidence",
        "currency_not_detected",
        "ocr_unavailable",
    ]


def test_totals_mismatch_lowers_confidence() -> None:
    install_document("invoice-mismatch.pdf")

    result = asyncio.run(
        extract_invoice(
            ExtractInvoiceInput.model_validate({"document_id": str(DOCUMENT_ID)}),
            CTX,
        )
    )

    assert result.data.base == Decimal("100.00")
    assert result.data.vat == Decimal("21.00")
    assert result.data.total == Decimal("122.00")
    assert result.data.confidence == 0.62
    assert result.data.needs_review is True
    assert result.warnings == ["totals_mismatch"]


def test_document_type_is_accepted() -> None:
    install_document("invoice-F-2026-0042.pdf")

    result = asyncio.run(
        extract_invoice(
            ExtractInvoiceInput.model_validate(
                {
                    "document_id": str(DOCUMENT_ID),
                    "document_type": DocumentType.budget,
                }
            ),
            CTX,
        )
    )

    assert result.data.number == "F-2026-0042"


def test_unconfigured_repository_fails_closed() -> None:
    with pytest.raises(ToolError) as error:
        run_result(document_id=str(DOCUMENT_ID))

    assert error.value.code == "provider_unavailable"
