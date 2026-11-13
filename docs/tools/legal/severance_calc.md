---
estado: v2
version: 0.1.0
tool: legal.severance_calc
---

# `legal.severance_calc` — Cálculo de indemnización por despido

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `legal.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (normativa laboral española) |
| Caché | n/a |
| Perfiles | `praxis-biz` |

## 2. Semántica exacta

Calcula una indemnización orientativa por extinción de contrato.

Tiempo de servicio: `days_of_service = end_date − start_date` (días naturales); `years_of_service = days_of_service / 365`.

| `dismissal_type` | Días por año | Límite |
|---|---|---|
| `objective` (despido objetivo) | 20 | 12 mensualidades = 360 días |
| `improper` (despido improcedente) | 33 | 24 mensualidades = 720 días |
| `temporary` (fin de contrato temporal) | 12 | sin límite |

Despido improcedente con antigüedad anterior al **12/02/2012** (doble tramo):

1. `pre_2012_days = días_hasta_2012-02-12 / 365 × 45`.
2. `post_2012_days = días_desde_2012-02-12 / 365 × 33`.
3. Si `pre_2012_days ≤ 720`: `indemnity_days = min(pre + post, 720)`.
4. Si `pre_2012_days > 720`: `indemnity_days = min(pre + post, 42 mensualidades = 1260 días)`.

Importe: `amount = gross_annual_salary / 365 × indemnity_days` (salario diario), redondeado a 2 decimales.

Reglas:

- `end_date > start_date`; `gross_annual_salary > 0`.
- Se usa el salario bruto anual incluyendo pagas extras; no se prorratean complementos variables salvo que estén incluidos.
- Redondeo: días con 2 decimales, importe con 2, años con 2.
- `cap_applied=true` si se aplicó el límite.
- No se aplican reducciones por despido objetivo procedente (20 días) ni mejoras de convenio; el `legal_reference` es orientativo.
- `is_estimated=false` para la fórmula, pero `legal_disclaimer_required=true`: debe validarlo un laboralista.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class DismissalType(str, Enum):
    objective = "objective"
    improper = "improper"
    temporary = "temporary"

class SeveranceInput(BaseModel):
    start_date: date
    end_date: date
    gross_annual_salary: Decimal = Field(gt=0, decimal_places=2)
    dismissal_type: DismissalType
    currency: str = "EUR"

    @model_validator(mode="after")
    def fechas(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date debe ser posterior a start_date")
        return self

class SeveranceBreakdown(BaseModel):
    pre_2012_days: Decimal | None
    post_2012_days: Decimal | None
    pre_2012_period_days: int | None
    post_2012_period_days: int | None

class SeveranceOutput(BaseModel):
    days_of_service: int
    years_of_service: Decimal
    indemnity_days: Decimal
    amount: Decimal
    cap_applied: bool
    breakdown: SeveranceBreakdown
    legal_reference: str
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Objetivo | 2018-01-01 → 2026-11-13, 30.000 € | 177,42 días, 14.582,85 € |
| Improcedente reciente | misma antigüedad | 292,75 días, 24.061,70 € |
| Improcedente con doble tramo | desde 2010-01-01, 36.000 € | 582,31 días, 57.433,54 € |
| Temporal | 2025-01-01 → 2026-11-13, 24.000 € | 22,39 días, 1.472,16 € |
| Tope objetivo | antigüedad muy larga | 360 días, `cap_applied=true` |
| Tope improcedente | antigüedad > 22 años | 720 días, `cap_applied=true` |
| Fechas invertidas | end ≤ start | error `invalid_params` |
| Salario cero | `gross_annual_salary=0` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "start_date": "2018-01-01",
    "end_date": "2026-11-13",
    "gross_annual_salary": "30000",
    "dismissal_type": "objective"
  },
  "output": {
    "days_of_service": 3238,
    "years_of_service": "8.87",
    "indemnity_days": "177.42",
    "amount": "14582.85",
    "cap_applied": false,
    "breakdown": { "pre_2012_days": null, "post_2012_days": null, "pre_2012_period_days": null, "post_2012_period_days": null },
    "legal_reference": "Art. 53.1.b ET (20 días/año, máx. 12 mensualidades)",
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "start_date": "2010-01-01",
    "end_date": "2026-11-13",
    "gross_annual_salary": "36000",
    "dismissal_type": "improper"
  },
  "output": {
    "days_of_service": 6160,
    "years_of_service": "16.88",
    "indemnity_days": "582.31",
    "amount": "57433.54",
    "cap_applied": false,
    "breakdown": {
      "pre_2012_days": "95.18",
      "post_2012_days": "487.13",
      "pre_2012_period_days": 772,
      "post_2012_period_days": 5388
    },
    "legal_reference": "DT 11ª ET (45 días/año antes de 12/02/2012 y 33 después, máx. 720 días)",
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "start_date": "2025-01-01",
    "end_date": "2026-11-13",
    "gross_annual_salary": "24000",
    "dismissal_type": "temporary"
  },
  "output": {
    "days_of_service": 681,
    "years_of_service": "1.87",
    "indemnity_days": "22.39",
    "amount": "1472.16",
    "cap_applied": false,
    "breakdown": { "pre_2012_days": null, "post_2012_days": null, "pre_2012_period_days": null, "post_2012_period_days": null },
    "legal_reference": "Art. 49.1.c ET (12 días/año)",
    "currency": "EUR"
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "calculation",
  "is_estimated": false,
  "currency": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Puede usar `legal.collective_agreement` para mejoras de convenio.
- Alimenta escenarios de coste laboral en `sim.hiring_simulator`.
- Combinable con `finance.cashflow_13w` para provisionar la indemnización.

## 8. Decisiones pendientes

- Mejoras voluntarias de convenio y límites por categoría.
- Salario regulador con complementos variables y en especie.
- Despido disciplinario procedente y nulidad (sin indemnización).
- Validación legal obligatoria antes de publicar la tool como definitiva.
