---
estado: v2
version: 0.1.0
tool: procurement.renewal_calendar
---

# `procurement.renewal_calendar` — Calendario de renovaciones

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `procurement.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | base de datos del tenant (RLS) |
| Caché | n/a |
| Perfiles | `praxis-biz` (asociación) |

## 2. Semántica exacta

Lista las renovaciones de contratos dentro de un horizonte temporal.

- `reference_date` por defecto es «hoy» en `Europe/Madrid` (fijable en tests).
- `horizon_end = reference_date + horizon_days`.
- `days_remaining = renewal_date − reference_date` (puede ser negativo).
- Se incluye un contrato si `renewal_date ≤ horizon_end` y (`renewal_date ≥ reference_date` o `include_expired=true`).
- `status`:
  - `expired` si `days_remaining < 0`.
  - `notice_due` si `0 ≤ days_remaining ≤ max(notice_days)` (ya toca avisar).
  - `upcoming` en el resto.
- `next_renewal` es la renovación no caducada más próxima (o `null`).
- `notice_due_count` = renovaciones con `status=notice_due`.
- Orden ascendente por `renewal_date`; empate por proveedor.

Reglas:

- `horizon_days ∈ [1, 365]`, por defecto `90`.
- `category` opcional filtra por categoría de contrato.
- `notice_days` viene de la regla de alerta asociada; si no existe, `[]` y `status` nunca será `notice_due` por aviso (solo `upcoming`/`expired`).
- Importes 2 decimales; fechas ISO 8601.
- Solo lectura; RLS por `company_id`.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

class RenewalCalendarInput(BaseModel):
    reference_date: date | None = None
    horizon_days: int = Field(default=90, ge=1, le=365)
    include_expired: bool = False
    category: str | None = None
    currency: str = "EUR"

class RenewalItem(BaseModel):
    contract_id: str
    supplier: str
    category: str
    renewal_date: date
    days_remaining: int
    notice_days: list[int]
    status: str  # notice_due | upcoming | expired
    estimated_annual_cost: Decimal | None

class RenewalCalendarOutput(BaseModel):
    reference_date: date
    horizon_end: date
    count: int
    notice_due_count: int
    next_renewal: date | None
    renewals: list[RenewalItem]
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Horizonte 90 días | ref. 2026-11-13 | 2 renovaciones (31-12 y 15-01) |
| Aviso pendiente | renovación 31-12, avisos [60,30,15] | `notice_due` (48 días) |
| Próxima | renovación 15-01, aviso [30] | `upcoming` (63 días) |
| Fuera de horizonte | renovación 01-03 | excluida |
| Caducada | renovación 01-11 | excluida salvo `include_expired` |
| Caducada incluida | `include_expired=true` | `expired`, `days_remaining=-12` |
| Filtro categoría | `category=energy` | solo energía |
| Horizonte inválido | `horizon_days=0` | error `invalid_params` |
| Sin renovaciones | horizonte corto | `count=0`, `next_renewal=null` |

## 5. Golden cases

Fixture `contracts-2026-11-13.json`, reloj fijo **2026-11-13**.

```json
{
  "input": { "reference_date": "2026-11-13", "horizon_days": 90 },
  "output": {
    "reference_date": "2026-11-13",
    "horizon_end": "2027-02-11",
    "count": 2,
    "notice_due_count": 1,
    "next_renewal": "2026-12-31",
    "currency": "EUR",
    "renewals": [
      {
        "contract_id": "c_001",
        "supplier": "Suministros García S.L.",
        "category": "supplies",
        "renewal_date": "2026-12-31",
        "days_remaining": 48,
        "notice_days": [60, 30, 15],
        "status": "notice_due",
        "estimated_annual_cost": "12000.00"
      },
      {
        "contract_id": "c_002",
        "supplier": "Eléctrica X",
        "category": "energy",
        "renewal_date": "2027-01-15",
        "days_remaining": 63,
        "notice_days": [30],
        "status": "upcoming",
        "estimated_annual_cost": "8400.00"
      }
    ]
  }
}
```

```json
{
  "input": { "reference_date": "2026-11-13", "horizon_days": 90, "include_expired": true },
  "output": {
    "count": 3,
    "renewals": [
      {
        "contract_id": "c_000",
        "supplier": "Mantenimiento Y S.L.",
        "category": "services",
        "renewal_date": "2026-11-01",
        "days_remaining": -12,
        "notice_days": [30],
        "status": "expired",
        "estimated_annual_cost": "3600.00"
      }
    ],
    "note": "Se muestran solo la renovación caducada; el resto son las dos del caso anterior"
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "database",
  "source_type": "database",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "list",
  "is_estimated": false,
  "currency": "EUR",
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Usa las reglas de `alerts.contract_renewal` para `notice_days`.
- Puede crear eventos con `calendar.create_event` (v3).
- Alimenta `procurement.rfp_generation` cuando una renovación requiere pliego.

## 8. Decisiones pendientes

- Exportación a iCalendar (`.ics`) y vista por proveedor.
- Renovaciones tácitas y preavisos legales por tipo de contrato.
- Coste estimado real (facturas) frente a coste de contrato.
- Sincronización con la agenda del usuario.
