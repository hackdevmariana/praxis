import io
import re
import time
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pdfplumber

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.money import quantize_money
from app.providers.cache import TTLCache
from app.providers.documents import get_document_repository, get_invoice_ocr
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.documents.extract_invoice.schemas import (
    ExtractInvoiceInput,
    ExtractInvoiceOutput,
    InvoiceLine,
)

_MAX_DOCUMENT_SIZE = 20 * 1024 * 1024
_EXTRACTION_VERSION = "1.0.0"

_CIF_RE = re.compile(r"\b([ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b")
_NUMBER_RE = re.compile(
    r"(?im)\b(?:factura|n[uú]mero|n[.ºo]\s*|fra(?:ctura)?)\s*[:#]?\s*"
    r"([A-Z0-9][A-Z0-9/-]{2,29})\b"
)
_DATE_TOKEN = r"(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})"
_LINE_RE = re.compile(
    r"^(?P<description>.+?)\s+"
    r"(?P<quantity>\d+(?:[.,]\d+)?)\s+"
    r"(?P<unit_price>\d+(?:[.,]\d{2,4}))\s+"
    r"(?P<vat_rate>\d{1,2}(?:[.,]\d+)?)\s*%\s+"
    r"(?P<line_total>\d+(?:[.,]\d{2}))\s*$",
    re.MULTILINE,
)
_SEPARATORS_RE = re.compile(r"[\s.\-]+")


@dataclass(frozen=True, slots=True)
class _CachedExtraction:
    output: ExtractInvoiceOutput
    warnings: tuple[str, ...]
    language: str | None
    processing_time_ms: int


_CACHE: TTLCache[_CachedExtraction] = TTLCache()


def _decimal(raw: str) -> Decimal:
    cleaned = raw.strip().replace(" ", "").replace("€", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as error:
        raise ValueError(f"Importe inválido: {raw}") from error


def _money(raw: str) -> Decimal:
    return quantize_money(_decimal(raw))


def _amount_after(text: str, pattern: str) -> Decimal | None:
    match = re.search(
        rf"(?im){pattern}\s*[:]?\s*([0-9][0-9.,]*)\s*(?:€|EUR)?",
        text,
    )
    return _money(match.group(1)) if match else None


def _date_after(text: str, *labels: str) -> Date | None:
    for label in labels:
        match = re.search(rf"(?im){label}\s*[:]?\s*{_DATE_TOKEN}", text)
        if match:
            return _parse_date(match.group(1))
    return None


def _parse_date(raw: str) -> Date | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _issuer(text: str) -> str | None:
    match = re.search(
        r"(?im)^\s*(?:emisor|proveedor|raz[oó]n social)\s*[:]?\s*(.+)$",
        text,
    )
    if match:
        return match.group(1).strip()
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if _CIF_RE.search(candidate):
            continue
        if lowered.startswith(("factura", "fecha", "vencimiento", "base", "iva", "total")):
            continue
        return candidate
    return None


def _currency(text: str) -> str | None:
    if re.search(r"\bEUR\b|€", text, re.IGNORECASE):
        return "EUR"
    if re.search(r"\bUSD\b|\$", text, re.IGNORECASE):
        return "USD"
    if re.search(r"\bGBP\b|£", text, re.IGNORECASE):
        return "GBP"
    return None


def _lines(text: str) -> list[InvoiceLine]:
    lines: list[InvoiceLine] = []
    for match in _LINE_RE.finditer(text):
        try:
            quantity = _decimal(match.group("quantity"))
            unit_price = _decimal(match.group("unit_price"))
            vat_rate = _decimal(match.group("vat_rate"))
            line_total = _money(match.group("line_total"))
        except ValueError:
            continue
        lines.append(
            InvoiceLine(
                description=match.group("description").strip(),
                quantity=quantity,
                unit_price=unit_price,
                vat_rate=vat_rate,
                line_total=line_total,
            )
        )
    return lines


def _confidence(fields: dict[str, bool]) -> float:
    weights = {
        "issuer": 0.05,
        "issuer_cif": 0.15,
        "number": 0.20,
        "date": 0.15,
        "base": 0.10,
        "vat": 0.10,
        "total": 0.20,
        "currency": 0.05,
    }
    coverage = sum(weight for name, weight in weights.items() if fields[name])
    return round(0.93 * coverage, 2)


def _extract(text: str, *, ocr_used: bool = False) -> tuple[ExtractInvoiceOutput, list[str]]:
    if len(text.strip()) < 100:
        warnings = ["low_confidence", "currency_not_detected"]
        warnings.append("ocr_no_text" if ocr_used else "ocr_unavailable")
        return (
            ExtractInvoiceOutput(
                issuer=None,
                issuer_cif=None,
                number=None,
                date=None,
                due_date=None,
                lines=[],
                base=None,
                vat=None,
                total=None,
                currency=None,
                needs_review=True,
                confidence=0.0,
            ),
            warnings,
        )

    issuer = _issuer(text)
    cif_match = _CIF_RE.search(text)
    issuer_cif = _SEPARATORS_RE.sub("", cif_match.group(1)).upper() if cif_match else None
    number_match = _NUMBER_RE.search(text)
    number = number_match.group(1).upper() if number_match else None
    issue_date = _date_after(text, r"fecha(?:\s+de\s+emisi[oó]n)?", r"fecha\s+factura")
    due_date = _date_after(text, r"vencimiento", r"fecha\s+de\s+vencimiento")
    lines = _lines(text)
    base = _amount_after(text, r"base\s+imponible")
    vat = _amount_after(text, r"\biva\b(?:\s*\([^)]*\))?")
    total = _amount_after(text, r"\btotal\b(?:\s+factura)?")
    currency = _currency(text)

    warnings: list[str] = []
    if currency is None:
        warnings.append("currency_not_detected")
    if (
        base is not None
        and vat is not None
        and total is not None
        and abs(base + vat - total) > Decimal("0.02")
    ):
        warnings.append("totals_mismatch")

    confidence = _confidence(
        {
            "issuer": issuer is not None,
            "issuer_cif": issuer_cif is not None,
            "number": number is not None,
            "date": issue_date is not None,
            "base": base is not None,
            "vat": vat is not None,
            "total": total is not None,
            "currency": currency is not None,
        }
    )
    if "totals_mismatch" in warnings:
        confidence = max(0.0, round(confidence - 0.31, 2))

    return (
        ExtractInvoiceOutput(
            issuer=issuer,
            issuer_cif=issuer_cif,
            number=number,
            date=issue_date,
            due_date=due_date,
            lines=lines,
            base=base,
            vat=vat,
            total=total,
            currency=currency,
            needs_review=confidence < 0.70,
            confidence=confidence,
        ),
        warnings,
    )


@tool(
    name="documents.extract_invoice",
    version="1.0.0",
    title="Extraer datos de factura",
    permissions=["documents.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Extrae datos estructurados de una factura, albarán o presupuesto PDF "
        "ya subido al tenant. Usa pdfplumber y heurísticas deterministas; nunca "
        "inventa campos ausentes. Si no hay capa de texto, marca revisión manual "
        "porque el OCR aún no está configurado."
    ),
)
async def extract_invoice(
    params: ExtractInvoiceInput, ctx: ToolContext
) -> ToolResult[ExtractInvoiceOutput]:
    company_id = ctx.company_id or ""
    cache_key = (
        f"{company_id}:{params.document_id}:{params.document_type.value}:{_EXTRACTION_VERSION}"
    )
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return tool_result(
            cached.value.output,
            warnings=cached.value.warnings,
            metadata_extra={
                "source": "document",
                "source_type": "extraction",
                "source_detail": "pdfplumber",
                "valid_until": cached.valid_until,
                "result_type": "extraction",
                "confidence": cached.value.output.confidence,
                "processor": "pdfplumber",
                "extraction_version": _EXTRACTION_VERSION,
                "language_detected": cached.value.language,
                "processing_time_ms": 0,
                "ocr_used": False,
                "extraction_cached": True,
            },
        )

    repository = get_document_repository(ctx)
    document = await repository.get(company_id=company_id, document_id=params.document_id)
    if document is None:
        raise ToolError(
            "document_not_found",
            "El documento no existe en la empresa del usuario.",
            details={"document_id": str(params.document_id)},
        )
    if len(document.content) > _MAX_DOCUMENT_SIZE:
        raise ToolError(
            "document_too_large",
            "El documento supera el tamaño máximo permitido.",
        )
    if not document.content.startswith(b"%PDF-"):
        raise ToolError(
            "unsupported_format",
            "El documento no es un PDF válido.",
        )

    started = time.perf_counter()
    try:
        with pdfplumber.open(io.BytesIO(document.content)) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as error:
        raise ToolError(
            "unsupported_format",
            "No se pudo leer el PDF.",
        ) from error
    ocr_used = False
    if len(text.strip()) < 100:
        try:
            ocr_text = await get_invoice_ocr(ctx).extract_text(
                content=document.content,
                language=params.language,
            )
        except ToolError as error:
            if error.code != ErrorCode.PROVIDER_UNAVAILABLE:
                raise
        else:
            if ocr_text.strip():
                text = ocr_text
                ocr_used = True

    processing_time_ms = int((time.perf_counter() - started) * 1000)

    language = params.language
    if language is None and re.search(r"(?i)\b(factura|albar[aá]n|presupuesto)\b", text):
        language = "es"

    output, warnings = _extract(text, ocr_used=ocr_used)
    cached = _CACHE.set(
        cache_key,
        _CachedExtraction(
            output=output,
            warnings=tuple(warnings),
            language=language,
            processing_time_ms=processing_time_ms,
        ),
        timedelta(days=30),
    )

    return tool_result(
        output,
        warnings=warnings,
        metadata_extra={
            "source": "document",
            "source_type": "extraction",
            "source_detail": "tesseract" if ocr_used else "pdfplumber",
            "valid_until": cached.valid_until,
            "result_type": "extraction",
            "confidence": output.confidence,
            "processor": "tesseract" if ocr_used else "pdfplumber",
            "extraction_version": _EXTRACTION_VERSION,
            "language_detected": language,
            "processing_time_ms": processing_time_ms,
            "ocr_used": ocr_used,
            "extraction_cached": False,
        },
    )
