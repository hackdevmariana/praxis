---
estado: MVP
version: 1.0.0
tool: documents.generate_invoice
---

# `documents.generate_invoice` — Generar factura o albarán

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `documents.write` |
| Clasificación | `business` |
| read_only | false |
| idempotent | true (con `idempotency_key`) |
| requires_confirmation | true |
| Provider | WeasyPrint (HTML → PDF) |
| Caché | n/a |
| Perfiles | `praxis-biz` |
| Efectos | crea PDF en el VPS + registros `Document` e `Invoice` + `AuditLog` |

## 2. Semántica exacta

Genera una factura o albarán en PDF a partir de datos estructurados.

1. **Empresa emisora:** se toma del contexto autenticado (`company_id`); **no** se acepta como parámetro.
2. **Cliente:** `name` y, para factura, `cif` obligatorios. Si `country="ES"`, el CIF se valida con la misma lógica que `validate.spanish_id`; inválido → `invalid_tax_id`. Para clientes extranjeros se usa `vat_number`.
3. **Líneas:** `line_base = round(quantity × unit_price × (1 − discount_pct/100), 2)`.
4. **IVA por tipo:** las líneas se agrupan por `vat_rate` efectivo (`line.vat_rate` o `vat_rate` global). Por grupo: `group_vat = round(group_base × rate/100, 2)`. `vat = Σ group_vat`.
5. **Totales:** `base = Σ line_base`, `total = base + vat`.
6. **Albarán (`delivery_note`):** documento **no fiscal**; el IVA se fuerza a `0`, `total = base`, y el PDF lo indica.
7. **Numeración:** si `number` falta, se propone `{año}-{secuencia:04d}` (o `{serie}/{año}/{secuencia:04d}`), con secuencia por empresa y tipo, segura ante concurrencia. Si se aporta y ya existe en la empresa → `conflict`.
8. **Vencimiento:** `due_date` por defecto `date + 30 días`; si es anterior a `date` → `invalid_params`.
9. **PDF:** HTML con plantilla saneada → WeasyPrint; se guarda con nombre opaco `UUID.pdf` fuera del webroot. `file_hash` SHA-256 en `Document`.
10. **Idempotencia:** `(tool, company_id, idempotency_key)` durante 30 días; si ya existe, devuelve el documento original con `deduplicated=true` y no regenera nada.
11. **Confirmación:** sin confirmación humana → `confirmation_required`. No se envía la factura por email en el MVP.

Reglas:

- Importes en `Decimal` con 2 decimales (`ROUND_HALF_UP`); salida como string.
- `quantity > 0`, `unit_price ≥ 0`, `discount_pct ∈ [0, 100]`.
- Fechas ISO 8601. `currency` ISO 4217.
- El número se normaliza a mayúsculas; formato `[A-Z0-9/-]{1,30}`.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class InvoiceDocumentType(str, Enum):
    invoice = "invoice"
    delivery_note = "delivery_note"

class ClientInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cif: str | None = Field(default=None, max_length=20)
    vat_number: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    postal_code: str | None = Field(default=None, max_length=10)
    municipality: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    country: str = Field(default="ES", min_length=2, max_length=2)
    email: str | None = Field(default=None, max_length=254)

class LineInput(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    unit_price: Decimal = Field(ge=0, decimal_places=4)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)

class GenerateInvoiceInput(BaseModel):
    client: ClientInput
    lines: list[LineInput] = Field(min_length=1, max_length=200)
    number: str | None = Field(default=None, pattern=r"^[A-Za-z0-9/-]{1,30}$")
    series: str | None = Field(default=None, max_length=10)
    date: date
    due_date: date | None = None
    vat_rate: Decimal = Field(default=Decimal("21"), ge=0, le=100)
    document_type: InvoiceDocumentType = InvoiceDocumentType.invoice
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=2000)
    payment_terms: str | None = Field(default=None, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def fechas(self):
        if self.due_date is not None and self.due_date < self.date:
            raise ValueError("due_date no puede ser anterior a date")
        return self

class GenerateInvoiceOutput(BaseModel):
    document_id: str
    invoice_id: str
    pdf_path: str
    number: str
    date: date
    due_date: date
    base: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    document_type: InvoiceDocumentType
    deduplicated: bool
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Factura 2 líneas 21% | 500 + 3×25 | base 575.00, vat 120.75, total 695.75 |
| Descuento por línea | 100 con 10% | base 90.00, vat 18.90, total 108.90 |
| Tipos mixtos | 100 @21% + 100 @10% | base 200.00, vat 31.00, total 231.00 |
| Albarán | `document_type=delivery_note` | vat 0.00, total = base |
| Sin número | `number` omitido | propone `2026-0007` |
| Número duplicado | número existente | error `conflict` |
| CIF inválido | `cif="B00000001"` | error `invalid_tax_id` |
| Cliente extranjero | `country=FR`, `vat_number` | se omite validación española |
| Vencimiento anterior | `due_date < date` | error `invalid_params` |
| Reintento misma clave | mismo `idempotency_key` | mismo `document_id`, `deduplicated=true` |
| Sin confirmación | llamada sin confirmar | error `confirmation_required` |

## 5. Golden cases

```json
{
  "input": {
    "client": {
      "name": "Hotel Sol S.L.",
      "cif": "B87654323",
      "address": "Calle del Mar 10",
      "postal_code": "28013",
      "municipality": "Madrid",
      "province": "Madrid",
      "country": "ES"
    },
    "lines": [
      { "description": "Mantenimiento mensual", "quantity": "1", "unit_price": "500.00", "vat_rate": "21" },
      { "description": "Repuestos", "quantity": "3", "unit_price": "25.00", "vat_rate": "21" }
    ],
    "date": "2026-11-13",
    "due_date": "2026-12-13",
    "vat_rate": "21",
    "document_type": "invoice",
    "idempotency_key": "factura-hotel-sol-2026-11"
  },
  "output": {
    "document_id": "7d2b1f10-0000-4000-8000-000000000010",
    "invoice_id": "9a4c3e20-0000-4000-8000-000000000020",
    "pdf_path": "/var/praxis/documents/7d2b1f10-0000-4000-8000-000000000010.pdf",
    "number": "2026-0007",
    "date": "2026-11-13",
    "due_date": "2026-12-13",
    "base": "575.00",
    "vat": "120.75",
    "total": "695.75",
    "currency": "EUR",
    "document_type": "invoice",
    "deduplicated": false
  }
}
```

```json
{
  "input": {
    "client": { "name": "Cliente Demo S.L.", "cif": "B12345674" },
    "lines": [
      { "description": "Servicio con descuento", "quantity": "1", "unit_price": "100.00", "discount_pct": "10", "vat_rate": "21" }
    ],
    "date": "2026-11-13",
    "idempotency_key": "factura-descuento-001"
  },
  "output": {
    "base": "90.00",
    "vat": "18.90",
    "total": "108.90",
    "document_type": "invoice",
    "deduplicated": false
  }
}
```

```json
{
  "input": {
    "client": { "name": "Hotel Sol S.L.", "cif": "B87654323" },
    "lines": [
      { "description": "Mantenimiento mensual", "quantity": "1", "unit_price": "500.00" },
      { "description": "Repuestos", "quantity": "3", "unit_price": "25.00" }
    ],
    "date": "2026-11-13",
    "document_type": "delivery_note",
    "idempotency_key": "albaran-hotel-sol-2026-11"
  },
  "output": {
    "base": "575.00",
    "vat": "0.00",
    "total": "575.00",
    "document_type": "delivery_note",
    "deduplicated": false
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "document_generator",
  "source_type": "internal",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "mutation",
  "is_estimated": false,
  "currency": "EUR",
  "idempotency_key": "factura-hotel-sol-2026-11",
  "effect": "created",
  "document_hash_sha256": "<sha256>",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": false
}
```

## 7. Composiciones

- Usa `finance.vat` para el cálculo de cuotas por grupo.
- Usa `validate.spanish_id` para el CIF del cliente.
- Puede nutrirse de `documents.extract_invoice` (datos de un presupuesto aceptado).
- En v2, envío por email y conciliación con `finance.cashflow_13w`.

## 8. Decisiones pendientes

- Pendiente: numeración fiscal por serie y ejercicio; validación con gestoría (¿reinicio anual?).
- Implementado: cálculo por líneas y grupos de IVA, numeración delegada a `DocumentStore`, renderizado delegado a `InvoiceRenderer`, HTML saneado e idempotencia central en el ejecutor.
- Implementado: renderizado real con WeasyPrint (`PRAXIS_PDF_RENDERER=weasyprint`) y almacén local con numeración persistente fuera del webroot (`PRAXIS_DOCUMENTS_ADAPTER=local`).
- Pendiente: persistencia de `Document`/`Invoice`/`AuditLog` y secuencia fiscal transaccional en base de datos.
- Pendiente: Veri*factu / TicketBAI y firma electrónica en v2; validación legal.
- Pendiente: plantillas por tenant (logo, colores, idioma) en v1.1; decisión de producto.
- Implementado: `pdf_path` y `document_hash_sha256` en la salida (v1).
- Pendiente: descarga firmada y almacenamiento en S3/MinIO en v2; requiere proveedor.
- Decidido: abonos y facturas rectificativas en v1.1 (`document_type=credit_note`).
