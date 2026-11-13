---
estado: MVP
version: 1.0.0
tool: calendar.deadline_remaining
---

# `calendar.deadline_remaining` — Días restantes hasta el cierre

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `datetime.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista + dataset de festivos (para días hábiles) |
| Caché | n/a |
| Perfiles | all |

## 2. Semántica exacta

Calcula cuánto queda hasta el cierre de un periodo (mes, trimestre o año).

1. **Periodo de referencia:** se deriva de `reference_date` (si falta, la fecha actual en `timezone`).
2. **Límites:**
   - `month`: del día 1 del mes a su último día.
   - `quarter`: del día 1 del trimestre a su último día (marzo, junio, septiembre o diciembre).
   - `year`: del 1 de enero al 31 de diciembre.
3. **`days_remaining`:** `deadline - reference_date` en días naturales (0 si es el mismo día).
4. **`business_days_remaining`:** días hábiles en `(reference_date, deadline]` (excluye la fecha de referencia, incluye el cierre), descontando festivos.
5. **Festivos:** nacionales siempre; autonómicos si `community`; locales si `municipality_code`.

Reglas:

- `reference_date` es una fecha, no un instante; `timezone` solo aplica si se omite y se usa «hoy».
- Si falta el dataset de festivos para el año → `warnings` con `holiday_dataset_incomplete`.
- Nunca se devuelve un número negativo de días: si `reference_date` cae en el cierre, ambos contadores son `0`.

## 3. Contrato Pydantic

```python
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field

class Period(str, Enum):
    month = "month"
    quarter = "quarter"
    year = "year"

class DeadlineInput(BaseModel):
    period: Period
    reference_date: date | None = None
    timezone: str = "Europe/Madrid"
    community: str | None = None
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$")

class DeadlineOutput(BaseModel):
    period: Period
    period_start: date
    deadline: date
    days_remaining: int
    business_days_remaining: int
    holidays_applied: list[dict]
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Mes | `period=month`, `reference_date=2026-11-13` | start `2026-11-01`, deadline `2026-11-30`, days `17`, business `11` |
| Trimestre | `period=quarter`, `reference_date=2026-11-13` | start `2026-10-01`, deadline `2026-12-31`, days `48`, business `32` |
| Año | `period=year`, `reference_date=2026-11-13` | start `2026-01-01`, deadline `2026-12-31`, days `48`, business `32` |
| Último día del mes | `period=month`, `reference_date=2026-11-30` | days `0`, business `0` |
| Febrero bisiesto | `period=month`, `reference_date=2028-02-15` | deadline `2028-02-29` |
| Sin fecha (hoy) | `period=month` | usa «hoy» en `timezone` |
| Periodo inválido | `period=week` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": { "period": "month", "reference_date": "2026-11-13" },
  "output": {
    "period": "month",
    "period_start": "2026-11-01",
    "deadline": "2026-11-30",
    "days_remaining": 17,
    "business_days_remaining": 11,
    "holidays_applied": []
  }
}
```

```json
{
  "input": { "period": "quarter", "reference_date": "2026-11-13" },
  "output": {
    "period": "quarter",
    "period_start": "2026-10-01",
    "deadline": "2026-12-31",
    "days_remaining": 48,
    "business_days_remaining": 32,
    "holidays_applied": [
      { "date": "2026-12-06", "name": "Día de la Constitución", "scope": "national" },
      { "date": "2026-12-08", "name": "Inmaculada Concepción", "scope": "national" },
      { "date": "2026-12-25", "name": "Navidad", "scope": "national" }
    ]
  }
}
```

```json
{
  "input": { "period": "month", "reference_date": "2026-11-30" },
  "output": {
    "period": "month",
    "period_start": "2026-11-01",
    "deadline": "2026-11-30",
    "days_remaining": 0,
    "business_days_remaining": 0,
    "holidays_applied": []
  }
}
```

```json
{
  "input": { "period": "month", "reference_date": "2028-02-15" },
  "output": {
    "period": "month",
    "period_start": "2028-02-01",
    "deadline": "2028-02-29",
    "days_remaining": 14,
    "business_days_remaining": 10,
    "holidays_applied": []
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic+seeder:holidays",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": "2026-12-31",
  "holiday_dataset_version": "2026.1",
  "result_type": "calculation",
  "is_estimated": false,
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Combinada con `datetime.business_days` para planificación de cierres.
- Puerta de entrada a `finance.cashflow_13w` (v2): cierres y vencimientos.
- Usada por `alerts.contract_renewal` para calcular hitos.

## 8. Decisiones pendientes

- ¿Añadir cierre fiscal (`FiscalCalendarRule`) como periodo? Propuesta: tool separada `calendar.tax_deadline` en v2.
- ¿Devolver también `weeks_remaining`? Propuesta: sí, campo opcional en v1.1.
- Verificar que el cómputo de días hábiles coincide exactamente con `datetime.business_days` (mismo helper interno).
