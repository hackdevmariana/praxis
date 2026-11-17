---
estado: MVP
version: 1.0.0
tool: alerts.contract_renewal
---

# `alerts.contract_renewal` — Avisos de renovación de contrato

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `alerts.write` |
| Clasificación | `business` |
| read_only | false |
| idempotent | true (con `idempotency_key`) |
| requires_confirmation | true |
| Provider | determinista (planificación interna) |
| Caché | n/a |
| Perfiles | `praxis-biz` |
| Efectos | crea `AlertRule` y `AlertEvent` pendientes; **no** envía notificaciones en el MVP |

## 2. Semántica exacta

Programa recordatorios de renovación a N días del vencimiento.

1. **Contrato:** debe existir en el tenant (`contract_id` con RLS); si no → `contract_not_found`.
2. **Fecha de referencia:** «hoy» según reloj del servidor en `Europe/Madrid` (fijable en tests).
3. **Renovación:** `renewal_date` debe ser **hoy o futura**; si es pasada → `invalid_params`.
4. **Avisos:** `notice_days` es una lista de enteros `[1, 365]`, sin duplicados; por defecto `[60, 30, 15]`.
5. **Disparos:** `trigger_at = renewal_date − notice_days` a las **09:00** en `Europe/Madrid` (offset correcto según DST).
6. **Filtrado:** los disparos ya pasados no se programan; se emite warning `notice_days_in_past` con los días omitidos.
7. **Salida:** `schedule` ordenado por `trigger_at` ascendente; `next_trigger_at` es el primer disparo pendiente (o `null` si no queda ninguno).
8. **Canal:** `none` (solo registro interno), `email` o `whatsapp`. En el MVP el canal se **almacena** pero no se envía nada; el envío llega en v2.
9. **Idempotencia:** se deduplica por `(tool, company_id, idempotency_key)` **y** por `(contract_id, renewal_date)` activo. Si ya existe una regla equivalente, se devuelve con `deduplicated=true` sin crear duplicados.
10. **Confirmación:** sin confirmación humana → `confirmation_required`.

Reglas:

- Cada disparo crea un `AlertEvent` con `status=pending`, `scheduled_at` y `channel`.
- Si el contrato no está activo, se programa igualmente pero con warning `contract_not_active`.
- Si `renewal_date` es hoy, todos los avisos quedan en el pasado → `schedule: []` y warning `no_future_triggers`.
- No se envían notificaciones externas en el MVP; `channel` no implica entrega.
- Fechas en ISO 8601 con offset; `Europe/Madrid`.

## 3. Contrato Pydantic

```python
from datetime import date, datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

class Channel(str, Enum):
    none = "none"
    email = "email"
    whatsapp = "whatsapp"

class ContractRenewalInput(BaseModel):
    contract_id: UUID
    renewal_date: date
    notice_days: list[int] = Field(default_factory=lambda: [60, 30, 15], min_length=1, max_length=10)
    channel: Channel = Channel.none
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("notice_days")
    @classmethod
    def validar_dias(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("notice_days no puede contener duplicados")
        if any(d < 1 or d > 365 for d in v):
            raise ValueError("notice_days debe estar entre 1 y 365")
        return v

class ScheduleEntry(BaseModel):
    days_before: int
    trigger_at: datetime
    channel: Channel
    status: str  # pending | skipped

class ContractRenewalOutput(BaseModel):
    alert_rule_id: str
    renewal_date: date
    next_trigger_at: datetime | None
    schedule: list[ScheduleEntry]
    deduplicated: bool
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Renovación futura | hoy 2026-11-13, renovación 2027-03-31 | 3 avisos: 2027-01-30, 03-01, 03-16 |
| Aviso ya pasado | renovación 2026-12-15 | 2 avisos (30 y 15 días), warning `notice_days_in_past` |
| Renovación hoy | `renewal_date=2026-11-13` | `schedule=[]`, warnings `notice_days_in_past` y `no_future_triggers` |
| Renovación pasada | `renewal_date=2026-11-12` | error `invalid_params` |
| Días duplicados | `[30,30]` | error `invalid_params` |
| Canal email | `channel=email` | se almacena, no se envía (MVP) |
| Contrato inexistente | UUID ajeno | error `contract_not_found` |
| Repetición misma clave | mismo `idempotency_key` | misma regla, `deduplicated=true` |
| Regla equivalente | otra clave, mismo contrato y fecha | devuelve la existente, `deduplicated=true` |
| Sin confirmación | llamada sin confirmar | error `confirmation_required` |

## 5. Golden cases

Reloj fijo: **2026-11-13T10:00:00+01:00**.

```json
{
  "input": {
    "contract_id": "11111111-1111-4111-8111-111111111111",
    "renewal_date": "2027-03-31",
    "notice_days": [60, 30, 15],
    "channel": "none",
    "idempotency_key": "renovacion-contrato-111-2027"
  },
  "output": {
    "alert_rule_id": "22222222-2222-4222-8222-222222222222",
    "renewal_date": "2027-03-31",
    "next_trigger_at": "2027-01-30T09:00:00+01:00",
    "schedule": [
      { "days_before": 60, "trigger_at": "2027-01-30T09:00:00+01:00", "channel": "none", "status": "pending" },
      { "days_before": 30, "trigger_at": "2027-03-01T09:00:00+01:00", "channel": "none", "status": "pending" },
      { "days_before": 15, "trigger_at": "2027-03-16T09:00:00+01:00", "channel": "none", "status": "pending" }
    ],
    "deduplicated": false
  }
}
```

```json
{
  "input": {
    "contract_id": "33333333-3333-4333-8333-333333333333",
    "renewal_date": "2026-12-15",
    "notice_days": [60, 30, 15],
    "channel": "email",
    "idempotency_key": "renovacion-contrato-333-2026"
  },
  "output": {
    "alert_rule_id": "44444444-4444-4444-8444-444444444444",
    "renewal_date": "2026-12-15",
    "next_trigger_at": "2026-11-15T09:00:00+01:00",
    "schedule": [
      { "days_before": 30, "trigger_at": "2026-11-15T09:00:00+01:00", "channel": "email", "status": "pending" },
      { "days_before": 15, "trigger_at": "2026-11-30T09:00:00+01:00", "channel": "email", "status": "pending" }
    ],
    "deduplicated": false
  },
  "metadata": { "warnings": ["notice_days_in_past"] }
}
```

```json
{
  "input": {
    "contract_id": "55555555-5555-4555-8555-555555555555",
    "renewal_date": "2026-11-13",
    "notice_days": [60, 30, 15],
    "channel": "none",
    "idempotency_key": "renovacion-contrato-555-2026"
  },
  "output": {
    "alert_rule_id": "66666666-6666-4666-8666-666666666666",
    "renewal_date": "2026-11-13",
    "next_trigger_at": null,
    "schedule": [],
    "deduplicated": false
  },
  "metadata": { "warnings": ["notice_days_in_past", "no_future_triggers"] }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "internal",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "mutation",
  "is_estimated": false,
  "timezone": "Europe/Madrid",
  "idempotency_key": "renovacion-contrato-111-2027",
  "effect": "alert_rule_created",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Usa `datetime.calc` para la aritmética de fechas y `datetime.business_days` si en v1.1 se añaden avisos en días hábiles.
- Puede crear eventos en `calendar.create_event` (v1.1) además de `AlertEvent`.
- Alimenta `renewal_calendar` (v2) para vista unificada de renovaciones.

## 8. Decisiones pendientes

- Envío real de notificaciones (email/WhatsApp) y plantillas: v2.
- Recalcular avisos si cambia `renewal_date`: nueva regla o actualización in situ (propuesta: nueva versión de regla).
- Avisos en días hábiles (`business_days=true`) y hora configurable por tenant.
- Implementado: cálculo de disparos con DST, filtrado de avisos pasados, confirmación vía `ToolContext.confirmed`, idempotencia central en el ejecutor con alias por contrato/fecha y `ContractRepository` inyectable.
- Pendiente: persistencia real de contratos, `AlertRule`/`AlertEvent`, `AuditLog` y envío de notificaciones.
- Recurrencia (renovaciones anuales automáticas) y `next_cycle`.
