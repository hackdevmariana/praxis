from __future__ import annotations

import asyncio
import fcntl
import importlib
import io
import json
import shutil
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pdfplumber

from app.errors import ErrorCode, ToolError
from app.providers.documents import (
    StoredDocument,
)


class WeasyPrintInvoiceRenderer:
    """Renderiza HTML a PDF con WeasyPrint, importado de forma diferida."""

    def render_pdf(self, html: str) -> bytes:
        try:
            module = importlib.import_module("weasyprint")
        except ImportError as error:
            raise ToolError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "WeasyPrint no está instalado en este despliegue.",
            ) from error
        html_class = cast(Any, module).HTML
        return cast(bytes, html_class(string=html).write_pdf())


class TesseractInvoiceOcr:
    """OCR local con Tesseract sobre páginas PDF renderizadas por pdfplumber."""

    def __init__(self, *, languages: str = "spa+eng", tesseract_cmd: str = "tesseract") -> None:
        self.languages = languages
        self.tesseract_cmd = tesseract_cmd

    async def extract_text(self, *, content: bytes, language: str | None) -> str:
        return await asyncio.to_thread(self._extract_sync, content, language)

    def _extract_sync(self, content: bytes, language: str | None) -> str:
        if shutil.which(self.tesseract_cmd) is None:
            raise ToolError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Tesseract no está instalado en este despliegue.",
            )
        languages = {"es": "spa", "en": "eng"}.get(language or "", self.languages)
        pages: list[str] = []
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    image = page.to_image(resolution=200).original
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    result = subprocess.run(
                        [self.tesseract_cmd, "stdin", "stdout", "-l", languages],
                        input=buffer.getvalue(),
                        capture_output=True,
                        check=True,
                    )
                    pages.append(result.stdout.decode("utf-8", errors="replace"))
        except subprocess.CalledProcessError as error:
            raise ToolError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Tesseract no pudo procesar el documento.",
            ) from error
        return "\n".join(pages)


class LocalFileDocumentStore:
    """Almacén de documentos en sistema de archivos, con numeración persistente."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    async def number_exists(self, *, company_id: str, number: str, document_type: str) -> bool:
        company = self.company(company_id)
        with self.lock(company):
            return number in self.read_index(company)

    async def next_number(
        self,
        *,
        company_id: str,
        year: int,
        series: str | None,
        document_type: str,
    ) -> str:
        company = self.company(company_id)
        key = f"{document_type}_{year}_{series or 'DEFAULT'}"
        with self.lock(company):
            sequence_path = self.root / company / "sequences" / f"{key}.json"
            sequence_path.parent.mkdir(parents=True, exist_ok=True)
            current = json.loads(sequence_path.read_text()) if sequence_path.exists() else 0
            next_value = int(current) + 1
            sequence_path.write_text(json.dumps(next_value))
        prefix = series or document_type[:1].upper()
        return f"{prefix}-{year}-{next_value:04d}"

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
        company = self.company(company_id)
        with self.lock(company):
            target = self.root / company / f"{document_id}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pdf)
            index = self.read_index(company)
            index[number] = {"document_id": str(document_id), "filename": target.name}
            (self.root / company / "documents.json").write_text(json.dumps(index))
        return f"{company}/{document_id}.pdf"

    def read_index(self, company: str) -> dict[str, Any]:
        path = self.root / company / "documents.json"
        if not path.exists():
            return {}
        return cast(dict[str, Any], json.loads(path.read_text()))

    @contextmanager
    def lock(self, company: str) -> Generator[None]:
        lock_dir = self.root / ".locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        with (lock_dir / f"{company}.lock").open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def company(self, company_id: str) -> str:
        try:
            return str(UUID(company_id))
        except ValueError as error:
            raise ToolError(
                ErrorCode.INVALID_PARAMS,
                "company_id debe ser un UUID válido para el almacén local.",
            ) from error


class LocalFileDocumentRepository:
    """Lee documentos guardados por LocalFileDocumentStore."""

    def __init__(self, root: str | Path) -> None:
        self.store = LocalFileDocumentStore(root)

    async def get(self, *, company_id: str, document_id: UUID) -> StoredDocument | None:
        company = self.store.company(company_id)
        with self.store.lock(company):
            index = self.store.read_index(company)
            match: dict[str, Any] | None = None
            for metadata in index.values():
                if not isinstance(metadata, dict):
                    continue
                entry = cast(dict[str, Any], metadata)
                if entry.get("document_id") == str(document_id):
                    match = entry
                    break
            if match is None:
                return None
            path = self.store.root / company / str(match["filename"])
            if not path.exists():
                return None
            return StoredDocument(
                document_id=document_id,
                company_id=company_id,
                filename=str(match["filename"]),
                content=path.read_bytes(),
            )
