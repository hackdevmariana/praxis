---
estado: MVP
version: 1.0.0
tool: datetime.calc
---

# `datetime.calc` — Cálculos de fecha

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `datetime.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (`zoneinfo`) |
| Caché | n/a |
| Perfiles | all |

## 2. Semántica exacta

Operaciones sobre **fechas** (no horas), en la zona horaria indicada.

| `operation` | Entrada requerida | Resultado |
|---|---|---|
| `today` | — | Fecha actual en `timezone` |
| `add_days` | `date`, `days` | `date + days` (admite negativos) |
| `diff_days` | `date`, `date_b` | `date_b - date` en días (con signo) |
| `weekday` | `date` | Día de la semana ISO (1=lunes … 7=domingo) + nombre en castellano |
| `week_info` | `date` | Semana ISO, trimestre, semestre y día del año |

Reglas:

- `today` depende del reloj del servidor; en tests se fija con `time-machine`. El resultado es determinista para un instante dado.
- `add_days` y `diff_days` operan en **días naturales**, no laborables (para eso, `datetime.business_days`).
- `diff_days` es firmado: si `date_b < date`, devuelve un entero negativo.
- `week_info` usa la norma ISO 8601 (semana 1 = la que contiene el primer jueves del año); `iso_year` puede diferir del año natural en los bordes (p. ej. `2027-01-01` → `iso_week=53`, `iso_year=2026`).
- La zona horaria solo afecta a `today`; las demás operaciones trabajan sobre la fecha dada. `metadata.timezone` es siempre `Europe/Madrid` (zona de visualización), no el parámetro de entrada.

## 3. Contrato Pydantic

```python
from datetime import date
from enum import StrEnum
from pydantic import BaseModel, Field, model_validator

class Operation(StrEnum):
    today = "today"
    add_days = "add_days"
    diff_days = "diff_days"
    weekday = "weekday"
    week_info = "week_info"

class DateCalcInput(BaseModel):
    operation: Operation
    date: date | None = None
    date_b: date | None = None
    days: int | None = Field(default=None, ge=-36500, le=36500)
    timezone: str = "Europe/Madrid"

    @model_validator(mode="after")
    def requirements(self):
        req = {
            "add_days": ("date", "days"),
            "diff_days": ("date", "date_b"),
            "weekday": ("date",),
            "week_info": ("date",),
        }.get(self.operation.value, ())
        for field in req:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' es obligatorio para {self.operation.value}")
        return self

class DateCalcOutput(BaseModel):
    operation: Operation
    date: date | None = None
    days_diff: int | None = None
    weekday: int | None = None
    weekday_name: str | None = None
    iso_week: int | None = None
    iso_year: int | None = None
    quarter: int | None = None
    semester: int | None = None
    day_of_year: int | None = None
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Hoy (reloj fijo 2026-11-13T10:00Z) | `operation=today`, `timezone=Europe/Madrid` | `2026-11-13` |
| Hoy en otra zona | `operation=today`, `timezone=America/New_York` | `2026-11-13` (según reloj) |
| Sumar días | `operation=add_days`, `date=2026-11-13`, `days=10` | `2026-11-23` |
| Restar días | `operation=add_days`, `date=2026-11-13`, `days=-10` | `2026-11-03` |
| Cruzar año | `operation=add_days`, `date=2026-12-31`, `days=1` | `2027-01-01` |
| Año bisiesto | `operation=add_days`, `date=2028-02-28`, `days=1` | `2028-02-29` |
| Diferencia | `operation=diff_days`, `date=2026-11-01`, `date_b=2026-11-13` | `12` |
| Diferencia negativa | `operation=diff_days`, `date=2026-11-13`, `date_b=2026-11-01` | `-12` |
| Día de la semana | `operation=weekday`, `date=2026-11-13` | `weekday=5`, `weekday_name=viernes` |
| Semana ISO | `operation=week_info`, `date=2026-11-13` | `iso_week=46`, `iso_year=2026`, `quarter=4`, `semester=2`, `day_of_year=317` |
| Semana 1 | `operation=week_info`, `date=2026-01-01` | `iso_week=1`, `iso_year=2026`, `quarter=1`, `semester=1`, `day_of_year=1` |
| Borde ISO | `operation=week_info`, `date=2027-01-01` | `iso_week=53`, `iso_year=2026`, `quarter=1`, `semester=1`, `day_of_year=1` |
| Falta `date` | `operation=add_days`, sin `date` | error `invalid_params` |
| Zona inválida | `timezone=Europe/Atlantis` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": { "operation": "add_days", "date": "2026-11-13", "days": 10 },
  "output": { "operation": "add_days", "date": "2026-11-23" }
}
```

```json
{
  "input": { "operation": "diff_days", "date": "2026-11-01", "date_b": "2026-11-13" },
  "output": { "operation": "diff_days", "days_diff": 12 }
}
```

```json
{
  "input": { "operation": "weekday", "date": "2026-11-13" },
  "output": { "operation": "weekday", "weekday": 5, "weekday_name": "viernes" }
}
```

```json
{
  "input": { "operation": "week_info", "date": "2026-11-13" },
  "output": {
    "operation": "week_info",
    "iso_week": 46,
    "iso_year": 2026,
    "quarter": 4,
    "semester": 2,
    "day_of_year": 317
  }
}
```

```json
{
  "input": { "operation": "today", "timezone": "Europe/Madrid" },
  "output": { "operation": "today", "date": "2026-11-13" },
  "note": "Requiere reloj fijo en el test (time-machine)"
}
```

Los campos omitidos en un golden toman el valor por defecto del contrato (`null`).

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "calculation",
  "is_estimated": false,
  "confidence": null,
  "unit_system": "metric",
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": false
}
```

## 7. Composiciones

- Base de `calendar.deadline_remaining` y `datetime.business_days`.
- Usada por `alerts.contract_renewal` para calcular fechas de aviso.
- En la capa de canal, `dateparser` extrae fechas de mensajes y luego se llama a esta tool con fechas ya normalizadas.

## 8. Decisiones pendientes

- Decidido: `add_business_days` se mantiene en `datetime.business_days`.
- Decidido: parámetro `language` para `weekday_name` localizado en v2.
- Implementado: nombres de día estables en castellano sin acentos (`miercoles`).
