---
estado: MVP
version: 0.1.0
---

# Conectores e integraciones

`praxis-biz` conecta la instalación con servicios externos del tenant mediante **conectores**. En el MVP solo se implementa **Google Calendar** (OAuth por usuario). El resto se documenta como backlog.

## Modelo

| Entidad | Función |
|---|---|
| `Integration` | Conexión de una empresa/usuario a un proveedor. Estado, scopes, cursor de sync. |
| `IntegrationCredential` | Credenciales cifradas (access/refresh token, api key) con rotación. |
| `SyncLog` | Historial de sincronizaciones (operación, cursor, contadores, errores). |

Ver [`05-data-models.md`](05-data-models.md).

## OAuth: Google Calendar (MVP)

- **Por usuario:** cada persona conecta su cuenta. Permite separar agenda personal y de empresa.
- Scopes mínimos: lectura y escritura de eventos (`calendar.events`).
- Flujo OAuth 2.0 implementado con refresh token provisionado por instalación; la consola de consentimiento y el almacenamiento cifrado de tokens por usuario son responsabilidad del despliegue.
- El `calendar_id` distingue calendario (personal, empresa, recurso).
- Escritura (`calendar.create_event`) requiere `requires_confirmation: true`, `idempotency_key` y guarda un espejo en `calendar_events` cuando se activa `PRAXIS_EVENT_REPOSITORY=sql`.
- Las tools consumen un `CalendarConnector` inyectable. Sin conector configurado fallan con `connector_not_connected`; token caducado → `connector_auth_expired`.
- Activación: `PRAXIS_CALENDAR_ADAPTER=google` con `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REFRESH_TOKEN`, o `PRAXIS_GOOGLE_ACCESS_TOKEN` para cuentas de servicio.

### Sincronización

- **Incremental** con `syncToken` de Google; `sync_cursor` en `Integration`.
- Webhooks (push channels) como v2; en MVP, sincronización bajo demanda al listar eventos.
- `SyncLog` registra `full_sync` / `incremental` con contadores y errores.
- Si el token caduca o se revoca → `status: expired|revoked` y aviso al usuario.

### Datos y privacidad

- Los eventos son `personal`: RLS por `company_id` y cifrado de campos sensibles.
- No se sincronizan más campos de los necesarios para las tools.
- El usuario puede revocar el conector y borrar sus credenciales.

## Conectores de backlog

| Conector | Tipo | Uso | Estado |
|---|---|---|---|
| Microsoft 365 / Outlook | OAuth | Agenda y correo | v2 |
| Holded / Contasimple | API key | Facturación y contabilidad | v2 |
| GoCardless (PSD2) | OAuth | Movimientos bancarios, tesorería | v2 |
| WhatsApp Business API | API key/webhook | Notificaciones y canal | v2 |
| Stripe / Redsys | API key | Pagos y enlaces QR | backlog |
| Google Search Console | OAuth | SEO y palabras clave | backlog |
| Meta / LinkedIn | OAuth | Publicación de contenidos | backlog |

## Patrón de conector

Todo conector implementa:

1. **Autenticación:** OAuth o API key; credenciales cifradas.
2. **Descubrimiento:** capacidades y scopes disponibles.
3. **Sincronización:** full e incremental con cursores.
4. **Errores:** backoff y circuit breaker objetivo; reintentos con `stamina` pendientes de estandarizar.
5. **Revocación:** limpieza de credenciales y datos asociados.
6. **Auditoría:** `SyncLog` y `AuditLog`.

## Reglas

- Un conector nunca expone datos de otro tenant.
- Las credenciales nunca se registran en logs.
- La sincronización es idempotente y reanudable por cursor.
- Si un conector falla, las tools dependientes devuelven `provider_unavailable` con `metadata.errors`; nunca datos inventados.
- Los scopes se solicitan al mínimo necesario y se documentan al usuario.

## Fuera del MVP

- Sincronización por webhooks.
- Conectores contables y bancarios.
- Múltiples cuentas por proveedor (solo una por usuario en MVP).
