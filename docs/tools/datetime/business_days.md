---
estado: MVP
version: 1.0.0
tool: datetime.business_days
---

# `datetime.business_days` — Días hábiles con festivos

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `datetime.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | dataset de festivos (seeder) |
| Caché | n/a |
| Perfiles | all |

## 2. Semántica exacta

Cuenta días hábiles (lunes a viernes) entre dos fechas, excluyendo festivos nacionales, autonómicos y locales.

1. **Rango:** `start` **inclusivo**, `end` **exclusivo** por defecto. Si `include_end=true`, `end` se incluye.
2. **Fin de semana:** sábado y domingo nunca cuentan.
3. **Festivos aplicados:**
   - Nacionales (siempre).
   - Autonómicos si se indica `community`.
   - Locales si se indica `municipality_code` (código INE de 5 dígitos).
4. **Cómputo:** se recorren los días del rango y se cuentan los que son laborables y no festivos.
5. **Salida:** número de días hábiles, días naturales y lista de festivos aplicados con su ámbito.

Reglas:

- Si `start > end` → error `invalid_range`.
- Si `start == end`: `0` sin `include_end`; `1` si ese día es laborable y no festivo y `include_end=true`.
- Si se pide festivo local sin datos para ese municipio → `warnings` con `local_holidays_unavailable`, y se calcula sin locales (nunca se inventan).
- Si el rango cruza años sin dataset → `warnings` con `holiday_dataset_incomplete`.
- El dataset de festivos está versionado (ver `metadata.holiday_dataset_version` y `valid_until`).

## 3. Contrato Pydantic

```python
from datetime import date
from pydantic import BaseModel, Field, model_validator

class BusinessDaysInput(BaseModel):
    start: date
    end: date
    community: str | None = None
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    include_end: bool = False

    @model_validator(mode="after")
    def rango(self):
        if self.start > self.end:
            raise ValueError("start no puede ser posterior a end")
        return self

class HolidayApplied(BaseModel):
    date: date
    name: str
    scope: str  # national | autonomous | local

class BusinessDaysOutput(BaseModel):
    business_days: int
    calendar_days: int
    holidays_applied: list[HolidayApplied]
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Enero con festivos nacionales | `start=2026-01-01`, `end=2026-01-08` | `business_days=3`, festivos: 01-01, 01-06 |
| Semana Santa | `start=2026-04-01`, `end=2026-04-08` | `business_days=4`, festivo: 04-03 (Viernes Santo) |
| Sin festivos | `start=2026-11-02`, `end=2026-11-09` | `business_days=5` |
| Incluir fin | `start=2026-11-02`, `end=2026-11-06`, `include_end=true` | `business_days=5` |
| Mismo día (exclusivo) | `start=end=2026-11-13` | `business_days=0` |
| Mismo día (inclusivo) | `start=end=2026-11-13`, `include_end=true` | `business_days=1` |
| Fin de semana completo | `start=2026-11-14`, `end=2026-11-16` | `business_days=0` |
| Rango invertido | `start=2026-11-13`, `end=2026-11-01` | error `invalid_params` |
| Local sin datos | `municipality_code=99999` | warning `local_holidays_unavailable` |

## 5. Golden cases

```json
{
  "input": { "start": "2026-01-01", "end": "2026-01-08" },
  "output": {
    "business_days": 3,
    "calendar_days": 7,
    "holidays_applied": [
      { "date": "2026-01-01", "name": "Año Nuevo", "scope": "national" },
      { "date": "2026-01-06", "name": "Epifanía del Señor", "scope": "national" }
    ]
  }
}
```

```json
{
  "input": { "start": "2026-04-01", "end": "2026-04-08" },
  "output": {
    "business_days": 4,
    "calendar_days": 7,
    "holidays_applied": [
      { "date": "2026-04-03", "name": "Viernes Santo", "scope": "national" }
    ]
  }
}
```

```json
{
  "input": { "start": "2026-11-02", "end": "2026-11-09" },
  "output": { "business_days": 5, "calendar_days": 7, "holidays_applied": [] }
}
```

```json
{
  "input": { "start": "2026-11-02", "end": "2026-11-06", "include_end": true },
  "output": { "business_days": 5, "calendar_days": 5, "holidays_applied": [] }
}
```

```json
{
  "input": { "start": "2026-11-13", "end": "2026-11-13" },
  "output": { "business_days": 0, "calendar_days": 0, "holidays_applied": [] }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "seeder:holidays",
  "source_type": "database",
  "source_detail": "BOE + comunidades autónomas + datos.gob.es",
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

- Usada por `calendar.deadline_remaining` para días hábiles restantes.
- Usada por `alerts.contract_renewal` para contar plazos en días hábiles.
- Usada por `finance.cashflow_13w` (v2) para fechas de vencimiento.

## 8. Decisiones pendientes

- ¿Añadir `add_business_days(start, days)` como operación? Propuesta: nueva operación en v1.1.
- ¿Cómo tratar festivos que caen en fin de semana (traslado autonómico)? Depende del dataset por comunidad; documentar por año.
- Origen y mantenimiento de festivos locales: `datos.gob.es` + BOE; validar cobertura por municipio.
