---
estado: MVP
version: 1.0.0
tool: calendar.list_events
---

# `calendar.list_events` — Listar eventos de agenda

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `calendar.read` |
| Clasificación | `personal` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | Google Calendar (conector OAuth por usuario) |
| Caché | 60 s |
| Perfiles | `praxis-biz` |

## 2. Semántica exacta

Lista los eventos del calendario del **usuario autenticado** que se solapan con `[start, end)`.

- **Identidad:** se toma del contexto de autenticación (OAuth del usuario). **Nunca** se acepta `user_id` como parámetro; sería un salto de tenant.
- `calendar_id` por defecto `primary`; distingue calendario personal, de empresa o de recurso.
- Se devuelven eventos que **solapan** el rango: `event.start < end` y `event.end > start`.
- Los eventos recurrentes se expanden (`singleEvents=true`) y se ordenan por inicio ascendente.
- Eventos de día completo: `start`/`end` son fechas (`YYYY-MM-DD`), `is_all_day=true`; `end` es exclusivo (norma de Google).
- `max_results ∈ [1, 250]`, por defecto `50`. Si hay más, se devuelve `next_page_token`.
- Fechas naive se interpretan en `timezone` (por defecto `Europe/Madrid`); las que llevan offset se respetan.
- Si `start ≥ end` → error `invalid_params`.
- Si no hay conector activo → `connector_not_connected`; token caducado o revocado → `connector_auth_expired`.
- Los datos son personales: RLS por `company_id` y cifrado de campos sensibles; no se cachean entre tenants.

## 3. Contrato Pydantic

```python
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class ListEventsInput(BaseModel):
    start: datetime
    end: datetime
    calendar_id: str = Field(default="primary", min_length=1, max_length=256)
    max_results: int = Field(default=50, ge=1, le=250)
    timezone: str = "Europe/Madrid"

    @model_validator(mode="after")
    def rango(self):
        if self.start >= self.end:
            raise ValueError("start debe ser anterior a end")
        return self

class CalendarEvent(BaseModel):
    id: str
    title: str
    start: str  # ISO 8601 datetime o date si all-day
    end: str
    location: str | None
    attendees: list[str]
    status: str  # confirmed | tentative | cancelled
    is_all_day: bool
    html_link: str | None

class ListEventsOutput(BaseModel):
    events: list[CalendarEvent]
    next_page_token: str | None
    timezone: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Día con dos eventos | `start=2026-11-13T00:00+01:00`, `end=2026-11-14T00:00+01:00` | 2 eventos ordenados |
| Solape parcial | evento 09:00–10:00, rango desde 09:30 | incluido |
| Evento de día completo | evento 2026-11-14 | `is_all_day=true`, fechas sin hora |
| Calendario de empresa | `calendar_id=empresa@grupo.com` | eventos de ese calendario |
| Rango invertido | `start` posterior a `end` | error `invalid_params` |
| `max_results` excedido | `max_results=0` | error `invalid_params` |
| Sin conector | usuario sin OAuth | error `connector_not_connected` |
| Token revocado | refresh inválido | error `connector_auth_expired` |

## 5. Golden cases

Fixture congelado `gcal-2026-11-13.json` (dos eventos en `primary`).

```json
{
  "input": {
    "start": "2026-11-13T00:00:00+01:00",
    "end": "2026-11-14T00:00:00+01:00",
    "max_results": 10
  },
  "output": {
    "next_page_token": null,
    "timezone": "Europe/Madrid",
    "events": [
      {
        "id": "evt_001",
        "title": "Reunión de equipo",
        "start": "2026-11-13T09:00:00+01:00",
        "end": "2026-11-13T10:00:00+01:00",
        "location": "Sala 1",
        "attendees": ["ana@example.com", "luis@example.com"],
        "status": "confirmed",
        "is_all_day": false,
        "html_link": "https://calendar.google.com/event?eid=evt_001"
      },
      {
        "id": "evt_002",
        "title": "Comida con cliente",
        "start": "2026-11-13T13:00:00+01:00",
        "end": "2026-11-13T14:30:00+01:00",
        "location": "Restaurante X",
        "attendees": ["ana@example.com"],
        "status": "tentative",
        "is_all_day": false,
        "html_link": "https://calendar.google.com/event?eid=evt_002"
      }
    ]
  }
}
```

```json
{
  "input": {
    "start": "2026-11-14T00:00:00+01:00",
    "end": "2026-11-15T00:00:00+01:00"
  },
  "output": {
    "events": [
      {
        "id": "evt_003",
        "title": "Festivo local",
        "start": "2026-11-14",
        "end": "2026-11-15",
        "location": null,
        "attendees": [],
        "status": "confirmed",
        "is_all_day": true,
        "html_link": null
      }
    ],
    "next_page_token": null,
    "timezone": "Europe/Madrid"
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "google_calendar",
  "source_type": "connector",
  "retrieved_at": "<now>",
  "valid_until": "<retrieved_at + 60s>",
  "result_type": "list",
  "is_estimated": false,
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Usada por `alerts.contract_renewal` para evitar duplicar recordatorios.
- Base de `calendar.create_event` (consultar disponibilidad antes de crear).
- Contexto para `sim.hiring_simulator` (v2): agenda de entrevistas.

## 8. Decisiones pendientes

- Paginación completa con `page_token` de entrada en v1.1.
- Filtro por `attendee` o `q` (texto) en v1.1.
- Microsoft 365 / Outlook como conector alternativo en v2 (misma interfaz).
- Confirmar política de caché de eventos personales (¿cifrado en reposo de la caché?).
