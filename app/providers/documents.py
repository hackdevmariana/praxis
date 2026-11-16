"""Injectable document storage and PDF rendering adapters."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from app.context import ToolContext
from app.errors import ErrorCode, ToolError


class DocumentStore(Protocol):
    async def number_exists(
        self,
        *,
        company_id: str,
        number: str,
        document_type: str,
    ) -> bool: ...

    async def next_number(
        self,
        *,
        company_id: str,
        year: int,
        series: str | None,
        document_type: str,
    ) -> str: ...

    async def save(
        self,
        *,
        company_id: str,
        document_id: UUID,
        document_type: str,
        number: str,
        issue_date: date,
        pdf: bytes,
    ) -> str: ...


class InvoiceRenderer(Protocol):
    def render_pdf(self, html: str) -> bytes: ...


class _UnconfiguredDocumentStore:
    async def number_exists(
        self,
        *,
        company_id: str,
        number: str,
        document_type: str,
    ) -> bool:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El almacén de documentos no está configurado.",
        )

    async def next_number(
        self,
        *,
        company_id: str,
        year: int,
        series: str | None,
        document_type: str,
    ) -> str:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El almacén de documentos no está configurado.",
        )

    async def save(
        self,
        *,
        company_id: str,
        document_id: UUID,
        document_type: str,
        number: str,
        issue_date: date,
        pdf: bytes,
    ) -> str:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El almacén de documentos no está configurado.",
        )


class _UnconfiguredInvoiceRenderer:
    def render_pdf(self, html: str) -> bytes:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El renderizador PDF no está configurado.",
        )


_store: DocumentStore = _UnconfiguredDocumentStore()
_renderer: InvoiceRenderer = _UnconfiguredInvoiceRenderer()


def get_document_store(ctx: ToolContext) -> DocumentStore:
    return _store


def get_invoice_renderer(ctx: ToolContext) -> InvoiceRenderer:
    return _renderer


def set_document_adapters(
    store: DocumentStore | None = None,
    renderer: InvoiceRenderer | None = None,
) -> None:
    global _store, _renderer
    _store = store or _UnconfiguredDocumentStore()
    _renderer = renderer or _UnconfiguredInvoiceRenderer()
