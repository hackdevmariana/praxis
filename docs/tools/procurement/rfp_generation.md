---
estado: v2
version: 0.1.0
tool: procurement.rfp_generation
---

# `procurement.rfp_generation` — Generación de pliego (RFP)

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `procurement.write` |
| Clasificación | `business` |
| read_only | false |
| idempotent | true (con `idempotency_key`) |
| requires_confirmation | true |
| Provider | interno (Markdown → PDF opcional) |
| Caché | n/a |
| Perfiles | `praxis-biz` (asociación) |
| Efectos | crea documento en el VPS + registro `Document` + `AuditLog`; no envía nada |

## 2. Semántica exacta

Genera un pliego de solicitud de ofertas (RFP) a partir de requisitos y criterios de evaluación.

1. **Validación:** al menos 1 requisito; criterios con nombres únicos y pesos que sumen **100 ± 0,01**; `deadline` futura; `budget_max ≥ 0` si se aporta.
2. **Documento:** Markdown saneado con secciones: objeto, alcance, requisitos, criterios, calendario, presupuesto máximo y datos de contacto. Si `document_format=pdf`, se convierte con WeasyPrint.
3. **Almacenamiento:** nombre opaco `UUID.md|pdf` fuera del webroot; `file_hash` SHA-256 en `Document`.
4. **Proveedores:** la lista se incluye en el documento como destinatarios previstos; **no** se envían invitaciones en v2 (el envío es v3).
5. **Idempotencia:** `(tool, company_id, idempotency_key)` durante 30 días; devuelve el documento existente con `deduplicated=true`.
6. **Confirmación:** sin confirmación humana → `confirmation_required`.
7. **Auditoría:** se registra usuario, tenant, tool y hash del documento.

Reglas:

- `title` no vacío; `scope_description` no vacío.
- `weight_pct ∈ [0, 100]`; la suma debe ser 100 (±0,01).
- `deadline > hoy` en `Europe/Madrid`.
- `default_language` fijo `es`; no se generan traducciones en v2.
- El documento generado es una plantilla editable: no constituye asesoramiento legal.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

class DocumentFormat(str, Enum):
    md = "md"
    pdf = "pdf"

class Criterion(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    weight_pct: Decimal = Field(ge=0, le=100)

class SupplierRef(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None

class RfpInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    scope_description: str = Field(min_length=1, max_length=5000)
    requirements: list[str] = Field(min_length=1, max_length=100)
    evaluation_criteria: list[Criterion] = Field(min_length=1, max_length=20)
    deadline: date
    budget_max: Decimal | None = Field(default=None, ge=0)
    contact_email: EmailStr
    suppliers: list[SupplierRef] = Field(default_factory=list, max_length=50)
    document_format: DocumentFormat = DocumentFormat.md
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("evaluation_criteria")
    @classmethod
    def criterios_unicos(cls, v):
        if len({c.name for c in v}) != len(v):
            raise ValueError("Los criterios deben tener nombres únicos")
        return v

    @model_validator(mode="after")
    def pesos(self):
        if abs(sum(c.weight_pct for c in self.evaluation_criteria) - Decimal("100")) > Decimal("0.01"):
            raise ValueError("Los pesos de los criterios deben sumar 100")
        return self

class RfpOutput(BaseModel):
    document_id: str
    path: str
    title: str
    deadline: date
    criteria_count: int
    suppliers_count: int
    format: DocumentFormat
    checksum_sha256: str
    deduplicated: bool
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| RFP completa | 3 requisitos, 5 criterios (100%), 3 proveedores | documento `.md`, hash, sin envío |
| Formato PDF | `document_format=pdf` | documento `.pdf` |
| Pesos 95% | criterios suman 95 | error `invalid_params` |
| Criterios duplicados | dos "Precio" | error `invalid_params` |
| Sin requisitos | lista vacía | error `invalid_params` |
| Deadline pasada | ayer | error `invalid_params` |
| Sin confirmación | llamada sin confirmar | error `confirmation_required` |
| Repetición | misma clave | `deduplicated=true` |

## 5. Golden cases

```json
{
  "input": {
    "title": "Suministro de aceite 2027",
    "category": "supplies",
    "scope_description": "Acuerdo marco anual para el suministro de aceite de oliva virgen extra.",
    "requirements": [
      "Capacidad de suministro mínima de 5.000 litros anuales",
      "Certificación de calidad vigente",
      "Entrega en máximo 72 horas desde pedido"
    ],
    "evaluation_criteria": [
      { "name": "Precio", "weight_pct": "30" },
      { "name": "Calidad", "weight_pct": "25" },
      { "name": "Plazo de entrega", "weight_pct": "20" },
      { "name": "Servicio", "weight_pct": "15" },
      { "name": "Sostenibilidad", "weight_pct": "10" }
    ],
    "deadline": "2026-12-15",
    "budget_max": "25000",
    "contact_email": "compras@asociacion.example",
    "suppliers": [
      { "name": "Aceites S.L.", "email": "ventas@aceites.example" },
      { "name": "Olivar S.A.", "email": "ofertas@olivar.example" },
      { "name": "Campo Verde S.L.", "email": null }
    ],
    "document_format": "md",
    "idempotency_key": "rfp-aceite-2027"
  },
  "output": {
    "document_id": "8c1d2e30-0000-4000-8000-000000000030",
    "path": "/var/praxis/documents/8c1d2e30-0000-4000-8000-000000000030.md",
    "title": "Suministro de aceite 2027",
    "deadline": "2026-12-15",
    "criteria_count": 5,
    "suppliers_count": 3,
    "format": "md",
    "checksum_sha256": "<sha256-del-documento>",
    "deduplicated": false
  }
}
```

```json
{
  "input": {
    "title": "Prueba",
    "category": "other",
    "scope_description": "Prueba",
    "requirements": ["Requisito"],
    "evaluation_criteria": [
      { "name": "Precio", "weight_pct": "60" },
      { "name": "Calidad", "weight_pct": "35" }
    ],
    "deadline": "2026-12-15",
    "contact_email": "compras@asociacion.example",
    "idempotency_key": "rfp-prueba-001"
  },
  "output": null,
  "error": { "code": "invalid_params", "message": "Los pesos de los criterios deben sumar 100" }
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
  "idempotency_key": "rfp-aceite-2027",
  "effect": "document_created",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa `procurement.compare_offers` una vez recibidas las ofertas.
- Alimenta `procurement.renewal_calendar` con el hito de adjudicación.
- En v3, envío a proveedores y recepción de ofertas.

## 8. Decisiones pendientes

- Pendiente: plantillas por sector y cláusulas legales revisadas; validación legal.
- Pendiente: envío de invitaciones y portal de recepción de ofertas; requiere API.
- Pendiente: firma electrónica y registro de comunicaciones; validación legal.
- Pendiente: idiomas (ES/EN) y monedas múltiples; decisión de producto.
