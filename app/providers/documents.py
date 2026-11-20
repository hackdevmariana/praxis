"""Injectable document storage and PDF rendering adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from app.context import ToolContext
from app.errors import ErrorCode, ToolError


@dataclass(frozen=True, slots=True)
class StoredDocument:
    document_id: UUID
    company_id: str
    filename: str
    content: bytes


class DocumentRepository(Protocol):
    async def get(self, *, company_id: str, document_id: UUID) -> StoredDocument | None: ...


class _UnconfiguredDocumentRepository:
    async def get(self, *, company_id: str, document_id: UUID) -> StoredDocument | None:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El repositorio de documentos no está configurado.",
        )


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


class ArtifactStore(Protocol):
    async def save_artifact(
        self,
        *,
        company_id: str,
        document_id: UUID,
        document_type: str,
        extension: str,
        content: bytes,
        index_key: str,
    ) -> str: ...


class InvoiceRenderer(Protocol):
    def render_pdf(self, html: str) -> bytes: ...


class InvoiceOcr(Protocol):
    async def extract_text(self, *, content: bytes, language: str | None) -> str: ...


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


class _UnconfiguredArtifactStore:
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


class _UnconfiguredInvoiceOcr:
    async def extract_text(self, *, content: bytes, language: str | None) -> str:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El OCR de facturas no está configurado.",
        )


_store: DocumentStore = _UnconfiguredDocumentStore()
_artifact_store: ArtifactStore = _UnconfiguredArtifactStore()
_renderer: InvoiceRenderer = _UnconfiguredInvoiceRenderer()
_repository: DocumentRepository = _UnconfiguredDocumentRepository()
_ocr: InvoiceOcr = _UnconfiguredInvoiceOcr()


def get_document_store(ctx: ToolContext) -> DocumentStore:
    return _store


def get_artifact_store(ctx: ToolContext) -> ArtifactStore:
    return _artifact_store


def set_artifact_store(store: ArtifactStore | None) -> None:
    global _artifact_store
    _artifact_store = store or _UnconfiguredArtifactStore()


def get_invoice_renderer(ctx: ToolContext) -> InvoiceRenderer:
    return _renderer


def get_document_repository(ctx: ToolContext) -> DocumentRepository:
    return _repository


def get_invoice_ocr(ctx: ToolContext) -> InvoiceOcr:
    return _ocr


def set_document_adapters(
    store: DocumentStore | None = None,
    renderer: InvoiceRenderer | None = None,
    ocr: InvoiceOcr | None = None,
) -> None:
    global _store, _renderer, _ocr
    _store = store or _UnconfiguredDocumentStore()
    _renderer = renderer or _UnconfiguredInvoiceRenderer()
    _ocr = ocr or _UnconfiguredInvoiceOcr()


def set_document_repository(repository: DocumentRepository | None) -> None:
    global _repository
    _repository = repository or _UnconfiguredDocumentRepository()
