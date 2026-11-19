---
estado: v2
version: 0.1.0
tool: legal.collective_agreement
---

# `legal.collective_agreement` — Convenio colectivo aplicable

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `legal.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | REGCON (MITES), snapshot versionado |
| Caché | 30 días |
| Perfiles | `praxis-biz`, `praxis-knowledge` |

## 2. Semántica exacta

Determina el convenio colectivo aplicable por actividad (CNAE) y provincia.

1. **Búsqueda:** convenios vigentes en `year` cuyo CNAE coincida con los 4 dígitos y cuya provincia coincida.
2. **Alternativas:** si no hay coincidencia exacta, se prueban el prefijo de 2 dígitos del CNAE y, después, la provincia. Cada aproximación reduce `confidence` y añade warning.
3. **Actividad:** si hay varias coincidencias, `activity_description` se usa para desempatar por similitud textual; si no basta, se devuelven `alternatives` y `needs_review=true`.
4. **Datos laborales:** se devuelven `minimum_annual_salary`, `annual_working_hours` y `vacation_days` del año solicitado, si la tabla salarial está publicada.
5. **Vigencia:** si el convenio no cubre `year`, se devuelve el último vigente con warning `outdated_agreement`.

Reglas:

- `cnae` de 4 dígitos (se acepta con puntos y se normaliza).
- `province` nombre oficial en castellano (p. ej. `Madrid`, `Barcelona`).
- `year ∈ [2020, 2030]`.
- Sin coincidencia → `agreement=null`, `alternatives=[]`, warning `no_match` (no es error).
- Importes 2 decimales; horas y días enteros.
- El resultado es informativo y no sustituye la consulta del boletín oficial; `legal_disclaimer_required=true`.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

class CollectiveAgreementInput(BaseModel):
    cnae: str = Field(pattern=r"^\d{2}\.?\d{2}$")
    province: str = Field(min_length=2, max_length=80)
    year: int = Field(ge=2020, le=2030)
    activity_description: str | None = Field(default=None, max_length=500)

class AgreementAlternative(BaseModel):
    agreement_name: str
    code: str
    confidence: Decimal
    reason: str

class CollectiveAgreementOutput(BaseModel):
    agreement_name: str | None
    code: str | None
    scope: str | None
    cnae: str
    province: str
    year: int
    minimum_annual_salary: Decimal | None
    annual_working_hours: int | None
    vacation_days: int | None
    valid_from: date | None
    valid_to: date | None
    confidence: Decimal
    alternatives: list[AgreementAlternative]
    needs_review: bool
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Coincidencia exacta | CNAE 5610, Madrid, 2026 | Hostelería Madrid, confianza 0.95 |
| CNAE con punto | `56.10` | se normaliza a `5610` |
| Solo prefijo | CNAE 5611 sin convenio específico | alternativa 56xx, warning |
| Sin coincidencia | CNAE 9999 | `agreement=null`, warning `no_match` |
| Año no cubierto | `year=2030` | último vigente, warning `outdated_agreement` |
| Varias coincidencias | misma provincia y CNAE | `needs_review=true`, alternatives |
| Provincia inválida | `province=""` | error `invalid_params` |
| Año fuera de rango | `year=2019` | error `invalid_params` |

## 5. Golden cases

Los golden cases están inline en esta spec; no hay fixture `regcon-2026.json` en `tests/fixtures` ni implementación/tests para esta tool v2.

```json
{
  "input": {
    "cnae": "5610",
    "province": "Madrid",
    "year": 2026,
    "activity_description": "Restaurante de cocina mediterránea"
  },
  "output": {
    "agreement_name": "Convenio Colectivo de Hostelería de la Comunidad de Madrid",
    "code": "28001245011999",
    "scope": "Hostelería",
    "cnae": "5610",
    "province": "Madrid",
    "year": 2026,
    "minimum_annual_salary": "18000.00",
    "annual_working_hours": 1800,
    "vacation_days": 30,
    "valid_from": "2026-01-01",
    "valid_to": "2026-12-31",
    "confidence": "0.95",
    "alternatives": [],
    "needs_review": false
  }
}
```

```json
{
  "input": { "cnae": "9999", "province": "Madrid", "year": 2026 },
  "output": {
    "agreement_name": null,
    "code": null,
    "scope": null,
    "minimum_annual_salary": null,
    "annual_working_hours": null,
    "vacation_days": null,
    "valid_from": null,
    "valid_to": null,
    "confidence": "0.00",
    "alternatives": [],
    "needs_review": true
  },
  "metadata": { "warnings": ["no_match"] }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "regcon",
  "source_type": "dataset",
  "retrieved_at": "<now>",
  "valid_until": "<snapshot_date + 30d>",
  "result_type": "lookup",
  "is_estimated": false,
  "confidence": 0.95,
  "dataset_version": "2026.1",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Alimenta `legal.severance_calc` con el salario regulador si no se aporta.
- Usada por `finance.business_kpi` para costes laborales de referencia.
- Base de `legal.company_risk` (convenio y actividad del proveedor).

## 8. Decisiones pendientes

- Pendiente: scraping/actualización de REGCON y validación legal de los datos.
- Pendiente: tablas salariales por categoría y antigüedad, no solo mínimo; dataset.
- Pendiente: convenios de ámbito estatal vs. autonómico y concurrencia; validación legal.
- Pendiente: búsqueda semántica de actividad con dataset propio (v3); dataset.
