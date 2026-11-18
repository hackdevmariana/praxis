---
estado: MVP
version: 1.0.0
tool: documents.extract_invoice
---

# `documents.extract_invoice` — Extraer datos de factura

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `documents.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true (por documento + tipo + versión de extracción) |
| requires_confirmation | false |
| Provider | `pdfplumber` / `markitdown`; OCR `Tesseract` |
| Caché | resultado persistido en `DocumentExtraction` |
| Perfiles | `praxis-biz`, `praxis-knowledge` |

## 2. Semántica exacta

Extrae datos estructurados de una factura, albarán o presupuesto PDF ya subido.

1. **Acceso:** el documento se busca por `document_id` **dentro del tenant** (RLS). Si no existe o es de otra empresa → `document_not_found`.
2. **Validación:** tipo real PDF (`python-magic`, no por extensión) y tamaño dentro del límite configurado; si no → `unsupported_format` / `document_too_large`.
3. **Texto:** extracción con `pdfplumber` (o `markitdown`). Si el texto es insuficiente (< 100 caracteres útiles) se aplica OCR con `Tesseract` (`spa+eng`).
4. **Parseo:** heurísticas + regex sobre texto; se normalizan CIF/NIF, fechas ISO, importes `Decimal` y divisa.
5. **Cuadre:** se comprueba `base + vat = total` (±0.02) y `Σ líneas = base`. Si no cuadra → warning `totals_mismatch` y baja confianza.
6. **Confianza:** media ponderada de campos críticos (número, fecha, total, CIF). Si `< 0.70` → `needs_review=true`.
7. **Idempotencia:** misma `(document_id, document_type, extraction_version)` devuelve la extracción almacenada; no se reprocesa salvo `force=true` (reservado a administradores).
8. **Nunca se inventan datos:** los campos no encontrados se devuelven `null`; la ausencia se refleja en `warnings` y `confidence`.

Reglas:

- Importes como **string decimal** (2 decimales) y fechas ISO 8601.
- `issuer_cif` se normaliza a mayúsculas sin espacios ni guiones.
- `currency` ISO 4217; si no se detecta, `null` + warning `currency_not_detected`.
- El adaptador OCR está pendiente: un PDF sin capa de texto se devuelve con `needs_review=true`, `confidence=0.0` y warning `ocr_unavailable`; cuando se instale, se marcará `processor="tesseract"`.
- No se usa un LLM para extraer importes en el MVP (determinismo y trazabilidad).

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field

class DocumentType(str, Enum):
    invoice = "invoice"
    delivery_note = "delivery_note"
    budget = "budget"

class ExtractInvoiceInput(BaseModel):
    document_id: UUID
    document_type: DocumentType = DocumentType.invoice
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")

class InvoiceLine(BaseModel):
    description: str
    quantity: Decimal | None
    unit_price: Decimal | None
    vat_rate: Decimal | None
    line_total: Decimal | None

class ExtractInvoiceOutput(BaseModel):
    issuer: str | None
    issuer_cif: str | None
    number: str | None
    date: date | None
    due_date: date | None
    lines: list[InvoiceLine]
    base: Decimal | None
    vat: Decimal | None
    total: Decimal | None
    currency: str | None
    needs_review: bool
    confidence: float
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Factura digital | PDF con texto, `invoice` | todos los campos, confianza 0.93 |
| Albarán | `document_type=delivery_note` | número y líneas, total sin IVA |
| Escaneado legible | PDF sin capa de texto | OCR, `processor=tesseract`, confianza 0.78 |
| Escaneado ilegible | OCR < 0.70 | `needs_review=true`, warning `low_confidence` |
| Totales no cuadran | base 100 + vat 21 ≠ total 122 | warning `totals_mismatch` |
| Documento de otro tenant | UUID ajeno | error `document_not_found` |
| No PDF | imagen JPG | error `unsupported_format` |
| Sin divisa | no se detecta | `currency=null`, warning |
| Repetición | mismo `document_id` | devuelve extracción almacenada |

## 5. Golden cases

Fixture `invoice-F-2026-0042.pdf` (texto embebido, 2 líneas).

```json
{
  "input": { "document_id": "3f1c2a9e-0000-4000-8000-000000000001", "document_type": "invoice" },
  "output": {
    "issuer": "Suministros García S.L.",
    "issuer_cif": "B12345674",
    "number": "F-2026-0042",
    "date": "2026-11-05",
    "due_date": "2026-12-05",
    "lines": [
      { "description": "Tornillos M8 (caja 100)", "quantity": "10", "unit_price": "4.50", "vat_rate": "21", "line_total": "45.00" },
      { "description": "Servicio de instalación", "quantity": "1", "unit_price": "120.00", "vat_rate": "21", "line_total": "120.00" }
    ],
    "base": "165.00",
    "vat": "34.65",
    "total": "199.65",
    "currency": "EUR",
    "needs_review": false,
    "confidence": 0.93
  }
}
```

```json
{
  "input": { "document_id": "3f1c2a9e-0000-4000-8000-000000000002", "document_type": "invoice" },
  "output": {
    "issuer": null,
    "issuer_cif": null,
    "number": null,
    "date": null,
    "due_date": null,
    "lines": [],
    "base": null,
    "vat": null,
    "total": null,
    "currency": null,
    "needs_review": true,
    "confidence": 0.0
  },
  "metadata": {
    "warnings": ["low_confidence", "currency_not_detected", "ocr_unavailable"],
    "processor": "pdfplumber"
  }
}
```

```json
{
  "input": { "document_id": "3f1c2a9e-0000-4000-8000-000000000003", "document_type": "invoice" },
  "output": {
    "base": "100.00",
    "vat": "21.00",
    "total": "122.00",
    "needs_review": true,
    "confidence": 0.62
  },
  "metadata": { "warnings": ["totals_mismatch"] }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "document",
  "source_type": "extraction",
  "source_detail": "pdfplumber",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "extraction",
  "is_estimated": false,
  "confidence": 0.93,
  "processor": "pdfplumber",
  "extraction_version": "1.0.0",
  "language_detected": "es",
  "processing_time_ms": 412,
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Alimenta `procurement.compare_offers` (presupuestos → `OfferInput`).
- Alimenta `documents.generate_invoice` solo como referencia; no se reutiliza el PDF.
- Usada por `finance.vat` para verificar cuotas y por `finance.kpi` (v2) para gastos.

## 8. Decisiones pendientes

- Decidido: umbral de confianza 0.70 por defecto; configurable por tenant en v1.1.
- Pendiente: facturas multi-página, abonos y rectificativas en v1.1; decisión de producto.
- Pendiente: OCR de tablas complejas; evaluar `camelot`/`tabula` antes de ampliar heurísticas.
- Implementado: validación de PDF por magic bytes y tamaño, extracción con `pdfplumber`, heurísticas para CIF, fechas, líneas y totales, caché de 30 días y advertencias de cuadre/confianza.
- Pendiente: OCR con Tesseract, `python-magic`, almacenamiento persistente de `DocumentExtraction` y soporte multi-página avanzado.
- Decidido: almacenar solo campos y hashes, no el texto extraído completo; minimización de datos.
