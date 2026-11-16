import asyncio
from datetime import date as Date
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ToolError
from app.providers.documents import set_document_adapters
from app.tools.documents.generate_invoice.schemas import (
    GenerateInvoiceInput,
    GenerateInvoiceOutput,
)
from app.tools.documents.generate_invoice.tool import generate_invoice

CTX = ToolContext(request_id="test", company_id="company-1", confirmed=True)
CLIENT = {"name": "Hotel Sol S.L.", "cif": "B87654323"}


class FakeDocumentStore:
    def __init__(self) -> None:
        self.sequences: dict[tuple[str, int, str], int] = {}
        self.numbers: set[str] = set()
        self.saved: list[dict[str, object]] = []

    async def number_exists(
        self,
        *,
        company_id: str,
        number: str,
        document_type: str,
    ) -> bool:
        return number in self.numbers

    async def next_number(
        self,
        *,
        company_id: str,
        year: int,
        series: str | None,
        document_type: str,
    ) -> str:
        key = (company_id, year, document_type)
        sequence = self.sequences.get(key, 0) + 1
        self.sequences[key] = sequence
        number = f"{series}/{year}/{sequence:04d}" if series else f"{year}-{sequence:04d}"
        self.numbers.add(number)
        return number

    async def save(
        self,
        *,
        company_id: str,
        document_id: UUID,
        document_type: str,
        number: str,
        issue_date: Date,
        pdf: bytes,
    ) -> str:
        self.saved.append(
            {
                "company_id": company_id,
                "document_id": document_id,
                "document_type": document_type,
                "number": number,
                "issue_date": issue_date,
                "pdf": pdf,
            }
        )
        return f"/var/praxis/documents/{document_id}.pdf"


class FakeInvoiceRenderer:
    def __init__(self) -> None:
        self.html: list[str] = []

    def render_pdf(self, html: str) -> bytes:
        self.html.append(html)
        return b"%PDF-1.4 fake"


def install_adapters(
    store: FakeDocumentStore | None = None,
    renderer: FakeInvoiceRenderer | None = None,
) -> tuple[FakeDocumentStore, FakeInvoiceRenderer]:
    document_store = store or FakeDocumentStore()
    invoice_renderer = renderer or FakeInvoiceRenderer()
    set_document_adapters(document_store, invoice_renderer)
    return document_store, invoice_renderer


def run_result(**kwargs: object) -> GenerateInvoiceOutput:
    return asyncio.run(generate_invoice(GenerateInvoiceInput.model_validate(kwargs), CTX)).data


def test_invoice_golden() -> None:
    store, _ = install_adapters()
    store.sequences[("company-1", 2026, "invoice")] = 6

    output = run_result(
        client=CLIENT,
        lines=[
            {
                "description": "Mantenimiento mensual",
                "quantity": "1",
                "unit_price": "500.00",
                "vat_rate": "21",
            },
            {
                "description": "Repuestos",
                "quantity": "3",
                "unit_price": "25.00",
                "vat_rate": "21",
            },
        ],
        date="2026-11-13",
        due_date="2026-12-13",
        vat_rate="21",
        document_type="invoice",
        idempotency_key="factura-hotel-sol-2026-11",
    )

    assert output.number == "2026-0007"
    assert output.base == Decimal("575.00")
    assert output.vat == Decimal("120.75")
    assert output.total == Decimal("695.75")
    assert output.due_date == Date(2026, 12, 13)
    assert output.pdf_path.endswith(f"/{output.document_id}.pdf")
    assert output.deduplicated is False
    assert store.saved[0]["pdf"] == b"%PDF-1.4 fake"


def test_line_discount() -> None:
    install_adapters()

    output = run_result(
        client={"name": "Cliente Demo S.L.", "cif": "B12345674"},
        lines=[
            {
                "description": "Servicio con descuento",
                "quantity": "1",
                "unit_price": "100.00",
                "discount_pct": "10",
                "vat_rate": "21",
            }
        ],
        date="2026-11-13",
        idempotency_key="factura-descuento-001",
    )

    assert output.base == Decimal("90.00")
    assert output.vat == Decimal("18.90")
    assert output.total == Decimal("108.90")
    assert output.due_date == Date(2026, 12, 13)


def test_mixed_vat_rates_are_grouped() -> None:
    install_adapters()

    output = run_result(
        client=CLIENT,
        lines=[
            {"description": "A", "quantity": "1", "unit_price": "100", "vat_rate": "21"},
            {"description": "B", "quantity": "1", "unit_price": "100", "vat_rate": "10"},
        ],
        date="2026-11-13",
        idempotency_key="factura-mixta-001",
    )

    assert output.base == Decimal("200.00")
    assert output.vat == Decimal("31.00")
    assert output.total == Decimal("231.00")


def test_delivery_note_forces_zero_vat_and_uppercases_number() -> None:
    install_adapters()

    output = run_result(
        client={"name": "Hotel Sol S.L."},
        lines=[{"description": "Mantenimiento", "quantity": "1", "unit_price": "500"}],
        number="alb-2026-1",
        date="2026-11-13",
        document_type="delivery_note",
        idempotency_key="albaran-hotel-sol-2026-11",
    )

    assert output.number == "ALB-2026-1"
    assert output.document_type == "delivery_note"
    assert output.vat == Decimal("0.00")
    assert output.total == Decimal("500.00")


def test_duplicate_number_is_conflict() -> None:
    store, _ = install_adapters()
    store.numbers.add("2026-0007")

    with pytest.raises(ToolError) as error:
        run_result(
            client=CLIENT,
            lines=[{"description": "A", "quantity": "1", "unit_price": "10"}],
            number="2026-0007",
            date="2026-11-13",
            idempotency_key="factura-duplicada-001",
        )

    assert error.value.code == "conflict"


def test_invalid_spanish_cif_is_rejected() -> None:
    install_adapters()

    with pytest.raises(ToolError) as error:
        run_result(
            client={"name": "Hotel Sol S.L.", "cif": "B00000001"},
            lines=[{"description": "A", "quantity": "1", "unit_price": "10"}],
            date="2026-11-13",
            idempotency_key="factura-cif-invalido-001",
        )

    assert error.value.code == "invalid_tax_id"


def test_foreign_client_uses_vat_number_without_spanish_validation() -> None:
    install_adapters()

    output = run_result(
        client={
            "name": "Client FR SARL",
            "vat_number": "FR12345678901",
            "country": "FR",
        },
        lines=[{"description": "A", "quantity": "1", "unit_price": "10"}],
        date="2026-11-13",
        idempotency_key="factura-cliente-fr-001",
    )

    assert output.total == Decimal("12.10")


def test_foreign_invoice_requires_vat_number() -> None:
    with pytest.raises(ValidationError):
        GenerateInvoiceInput.model_validate(
            {
                "client": {"name": "Client FR SARL", "country": "FR"},
                "lines": [{"description": "A", "quantity": "1", "unit_price": "10"}],
                "date": "2026-11-13",
                "idempotency_key": "factura-cliente-fr-002",
            }
        )


def test_due_date_before_issue_date_is_invalid() -> None:
    with pytest.raises(ValidationError):
        GenerateInvoiceInput.model_validate(
            {
                "client": CLIENT,
                "lines": [{"description": "A", "quantity": "1", "unit_price": "10"}],
                "date": "2026-11-13",
                "due_date": "2026-11-12",
                "idempotency_key": "factura-vencimiento-invalido",
            }
        )


def test_confirmation_is_required() -> None:
    install_adapters()
    unconfirmed = ToolContext(request_id="test", company_id="company-1")

    with pytest.raises(ToolError) as error:
        asyncio.run(
            generate_invoice(
                GenerateInvoiceInput.model_validate(
                    {
                        "client": CLIENT,
                        "lines": [
                            {
                                "description": "A",
                                "quantity": "1",
                                "unit_price": "10",
                            }
                        ],
                        "date": "2026-11-13",
                        "idempotency_key": "factura-sin-confirmar",
                    }
                ),
                unconfirmed,
            )
        )

    assert error.value.code == "confirmation_required"


def test_same_idempotency_key_does_not_render_twice() -> None:
    store, renderer = install_adapters()
    payload = {
        "client": CLIENT,
        "lines": [{"description": "A", "quantity": "1", "unit_price": "10"}],
        "date": "2026-11-13",
        "idempotency_key": "factura-idempotente-001",
    }

    first = run_result(**payload)
    second = run_result(**payload)

    assert first.deduplicated is False
    assert second.deduplicated is True
    assert second.document_id == first.document_id
    assert len(renderer.html) == 1
    assert len(store.saved) == 1


def test_html_escapes_client_and_line_content() -> None:
    _, renderer = install_adapters()

    run_result(
        client={"name": "<script>alert(1)</script>", "cif": "B87654323"},
        lines=[
            {
                "description": "<b>Servicio</b>",
                "quantity": "1",
                "unit_price": "10",
            }
        ],
        date="2026-11-13",
        idempotency_key="factura-escape-001",
    )

    html = renderer.html[0]
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b>Servicio</b>" not in html
    assert "&lt;b&gt;Servicio&lt;/b&gt;" in html


def test_unconfigured_adapters_fail_closed() -> None:
    with pytest.raises(ToolError) as error:
        run_result(
            client=CLIENT,
            lines=[{"description": "A", "quantity": "1", "unit_price": "10"}],
            date="2026-11-13",
            idempotency_key="factura-sin-adaptadores",
        )

    assert error.value.code == "provider_unavailable"
