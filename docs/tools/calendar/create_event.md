---
estado: MVP
version: 1.0.0
tool: calendar.create_event
---

# `calendar.create_event` — Crear evento

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `calendar.write` |
| Clasificación | `personal` |
| read_only | false |
| idempotent | true (con `idempotency_key`) |
| requires_confirmation | true |
| Provider | Google Calendar (conector OAuth por usuario) |
| Caché | n/a |
| Perfiles | `praxis-biz` |
| Efectos | escritura en Google Calendar; invitaciones solo si `send_notifications=true` |

## 2. Semántica exacta

Crea un evento en el calendario del **usuario autenticado**.

1. **Validación:** `title` no vacío; `start < end`; emails válidos; `timezone` IANA válido.
2. **Día completo:** si `all_day=true`, `start`/`end` se interpretan como fechas y `end` es **exclusivo** (un evento del 21 al 23 de diciembre se envía con `end=2026-12-24`). `timezone` no altera la fecha.
3. **Confirmación:** la ejecución exige confirmación humana. Sin ella → error `confirmation_required`.
4. **Idempotencia:** se deduplica por `(tool, company_id, idempotency_key)`. Si la clave ya existe, se devuelve el evento original con `deduplicated=true` y **no** se crea otro. Los registros de idempotencia se conservan 30 días.
5. **Invitaciones:** los asistentes se añaden al evento; los correos de invitación solo se envían si `send_notifications=true` (por defecto `false`).
6. **Escritura:** se llama a `events.insert` con el scope `calendar.events`. `calendar_id` por defecto `primary`.
7. **Auditoría:** toda creación genera `AuditLog` (usuario, tenant, tool, `idempotency_key`, `event_id`).

Reglas:

- No se acepta `user_id` como parámetro: la identidad sale del contexto de autenticación.
- Si el token no tiene scope de escritura → `permission_denied`.
- Si Google devuelve conflicto → `conflict`; si el token caducó → `connector_auth_expired`.
- `recurrence_rrule` (opcional) se pasa como `RRULE` a Google; se valida sintácticamente.
- La respuesta refleja el evento creado (incluida la hora tal como la devuelve Google).

## 3. Contrato Pydantic

```python
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, model_validator

class CreateEventInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start: datetime
    end: datetime
    calendar_id: str = Field(default="primary", min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=8000)
    location: str | None = Field(default=None, max_length=500)
    attendees: list[EmailStr] = Field(default_factory=list, max_length=100)
    all_day: bool = False
    timezone: str = "Europe/Madrid"
    send_notifications: bool = False
    recurrence_rrule: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def rango(self):
        if self.start >= self.end:
            raise ValueError("start debe ser anterior a end")
        return self

class CreateEventOutput(BaseModel):
    event_id: str
    html_link: str | None
    status: str
    start: str
    end: str
    created: datetime
    deduplicated: bool
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Crear cita | título, 10:00–11:00, 1 asistente | `event_id`, `status=confirmed`, `deduplicated=false` |
| Reintento misma clave | mismo `idempotency_key` | mismo `event_id`, `deduplicated=true` |
| Día completo | 2026-12-21 → 2026-12-24, `all_day=true` | evento 21–23 |
| Con invitación | `send_notifications=true` | Google envía correos |
| Sin confirmación | llamada sin confirmar | error `confirmation_required` |
| Sin scope escritura | token solo lectura | error `permission_denied` |
| Rango invertido | `start` posterior a `end` | error `invalid_params` |
| Email inválido | `attendees=["no-es-email"]` | error `invalid_params` |
| Clave inválida | `idempotency_key="x"` | error `invalid_params` |
| Token caducado | refresh revocado | error `connector_auth_expired` |

## 5. Golden cases

```json
{
  "input": {
    "title": "Demo PRAXIS",
    "start": "2026-11-16T10:00:00+01:00",
    "end": "2026-11-16T11:00:00+01:00",
    "attendees": ["ana@example.com"],
    "send_notifications": false,
    "idempotency_key": "demo-2026-11-16"
  },
  "output": {
    "event_id": "evt_abc123",
    "html_link": "https://calendar.google.com/event?eid=evt_abc123",
    "status": "confirmed",
    "start": "2026-11-16T10:00:00+01:00",
    "end": "2026-11-16T11:00:00+01:00",
    "created": "2026-11-13T12:00:00+01:00",
    "deduplicated": false
  }
}
```

```json
{
  "input": {
    "title": "Demo PRAXIS",
    "start": "2026-11-16T10:00:00+01:00",
    "end": "2026-11-16T11:00:00+01:00",
    "attendees": ["ana@example.com"],
    "idempotency_key": "demo-2026-11-16"
  },
  "output": {
    "event_id": "evt_abc123",
    "html_link": "https://calendar.google.com/event?eid=evt_abc123",
    "status": "confirmed",
    "start": "2026-11-16T10:00:00+01:00",
    "end": "2026-11-16T11:00:00+01:00",
    "created": "2026-11-13T12:00:00+01:00",
    "deduplicated": true
  },
  "note": "Reintento con la misma idempotency_key; no se crea un segundo evento"
}
```

```json
{
  "input": {
    "title": "Vacaciones",
    "start": "2026-12-21T00:00:00+01:00",
    "end": "2026-12-24T00:00:00+01:00",
    "all_day": true,
    "idempotency_key": "vacaciones-2026"
  },
  "output": {
    "event_id": "evt_vac001",
    "status": "confirmed",
    "start": "2026-12-21",
    "end": "2026-12-24",
    "deduplicated": false
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "google_calendar",
  "source_type": "connector",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "mutation",
  "is_estimated": false,
  "timezone": "Europe/Madrid",
  "idempotency_key": "demo-2026-11-16",
  "effect": "created",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Consumida por `alerts.contract_renewal` para crear recordatorios.
- Complementa a `calendar.list_events` (comprobar disponibilidad antes de crear).
- En v2, `calendar.update_event` y `calendar.cancel_event`.

## 8. Decisiones pendientes

- ¿Permitir crear en calendarios compartidos de empresa? Requiere rol y `calendar_id` autorizado (v1.1).
- Política de `reminders` y `conferenceData` (Meet) en v1.1.
- Recurrencia: interfaz amigable (`daily|weekly|monthly`) además de `RRULE`.
- Verificar el límite de asistentes de Google y el comportamiento con invitaciones externas.
