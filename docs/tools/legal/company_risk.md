---
estado: v2
version: 0.1.0
tool: legal.company_risk
---

# `legal.company_risk` — Riesgo de empresa

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `legal.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | BORME, Registro Concursal, listas de morosidad |
| Caché | 24 h |
| Perfiles | `praxis-biz`, `praxis-knowledge` |

## 2. Semántica exacta

Evalúa señales públicas de riesgo de una empresa (no es un scoring crediticio).

- **Fuentes:** BORME (actos sociales), Registro Concursal (concursos) y, si hay base legal y proveedor, listas de morosidad. Cada fuente se puede desactivar.
- **CIF:** si se aporta, se valida con la lógica de `validate.spanish_id`; inválido → `invalid_tax_id`.
- **Señales y pesos:** concurso activo `+60`; disolución/liquidación `+40`; morosidad `+40`; reducción de capital `+10`; cambio de administrador `+5`; otros actos negativos `+5`. Score limitado a `[0, 100]`.
- **Nivel:** `high` si `score ≥ 60`; `medium` si `≥ 30`; `low` si `< 30`; `unknown` si no se pudo consultar ninguna fuente.
- **Sin señales pero fuentes consultadas:** `low`, score `0` (no implica solvencia; solo ausencia de señales).
- **Sin datos disponibles:** `risk_level=unknown`, `score=null`, warning `no_sources_available`.
- Los datos se devuelven tal cual con fecha; no se infieren hechos no publicados.
- `is_estimated=true` (el score es una heurística) y `legal_disclaimer_required=true`.

Reglas:

- `signals` ordenadas por severidad descendente y fecha descendente.
- `sources_checked` lista las fuentes realmente consultadas.
- Cada señal incluye `source`, `type`, `date`, `description`, `severity` y `url` si existe.
- No se consultan datos personales de administradores más allá de lo publicado.

## 3. Contrato Pydantic

```python
from datetime import date, datetime
from pydantic import BaseModel, Field

class CompanyRiskInput(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    cif: str | None = Field(default=None, max_length=20)
    include_borme: bool = True
    include_concursal: bool = True
    include_delinquency: bool = False

class RiskSignal(BaseModel):
    source: str
    type: str
    date: date | None
    description: str
    severity: str  # low | medium | high
    url: str | None

class CompanyRiskOutput(BaseModel):
    company_name: str
    cif: str | None
    risk_level: str  # low | medium | high | unknown
    score: int | None
    signals: list[RiskSignal]
    sources_checked: list[str]
    checked_at: datetime
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Concurso + reducción | concurso 2026-09-01, reducción 2026-05-10 | score 70, `high` |
| Sin señales | fuentes consultadas, 0 señales | score 0, `low` |
| CIF inválido | `cif="B00000000"` | error `invalid_tax_id` |
| Fuente desactivada | `include_concursal=false` | no se consulta el registro |
| Sin proveedores | todas las fuentes caídas | `unknown`, warning |
| Morosidad sin base legal | `include_delinquency=true` no disponible | warning `delinquency_unavailable` |
| Empresa inexistente | sin coincidencias | `unknown`, warning `no_match` |

## 5. Golden cases

```json
{
  "input": {
    "company_name": "Construcciones Ejemplo S.L.",
    "cif": "B12345674",
    "include_borme": true,
    "include_concursal": true
  },
  "output": {
    "company_name": "Construcciones Ejemplo S.L.",
    "cif": "B12345674",
    "risk_level": "high",
    "score": 70,
    "sources_checked": ["borme", "registro_concursal"],
    "checked_at": "2026-11-13T10:00:00+01:00",
    "signals": [
      {
        "source": "registro_concursal",
        "type": "concurso_activo",
        "date": "2026-09-01",
        "description": "Concurso de acreedores activo",
        "severity": "high",
        "url": "https://www.publicidadconcursal.es/consulta-publica"
      },
      {
        "source": "borme",
        "type": "reduccion_capital",
        "date": "2026-05-10",
        "description": "Reducción de capital social",
        "severity": "medium",
        "url": "https://www.boe.es/diario_borme/"
      }
    ]
  }
}
```

```json
{
  "input": { "company_name": "Empresa Sana S.L.", "cif": "B87654323" },
  "output": {
    "risk_level": "low",
    "score": 0,
    "signals": [],
    "sources_checked": ["borme", "registro_concursal"]
  },
  "metadata": { "warnings": [] }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "borme+registro_concursal",
  "source_type": "external_api",
  "retrieved_at": "<now>",
  "valid_until": "<retrieved_at + 24h>",
  "result_type": "analysis",
  "is_estimated": true,
  "confidence": 0.85,
  "datasets_version": "2026.1",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa `validate.spanish_id` para el CIF.
- Alimenta `procurement.compare_offers` y `legal.collective_agreement` como contexto de proveedor.
- Base de alertas de riesgo de proveedores (v3).

## 8. Decisiones pendientes

- Contrato con el Registro Concursal y base legal para listas de morosidad.
- Matching por nombre (fuzzy) y falsos positivos; exigir CIF para resultados fiables.
- Score configurable por tenant y sector.
- Historial de señales y evolución temporal.
