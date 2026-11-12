---
estado: MVP
version: 0.1.0
---

# Seguridad y multi-tenancy

## Modelo de amenaza resumido

- **Aislamiento entre empresas:** el fallo más grave sería filtrar datos de un tenant a otro.
- **Herramientas con efectos:** crear eventos, generar facturas o programar alertas pueden causar daño si se invocan sin control.
- **Credenciales externas:** tokens OAuth y claves de API son objetivo de robo.
- **Datos personales:** nóminas, NIF, IBAN y agendas requieren protección reforzada (GDPR).

## Autenticación (MVP)

- **API key + JWT simple** para el servidor MCP. Sin OIDC/Keycloak en el MVP (v2).
- **API key:** enviada en cabecera; se almacena únicamente su hash con **Argon2id** (`argon2-cffi`). Nunca en claro.
- **JWT:** firmado por la instalación, con claims `sub` (user_id), `company_id`, `role`, `scopes`, `exp`. Vida corta y rotación.
- **MCP OAuth:** `authlib` como base para el flujo OAuth de Google Calendar (por usuario), no para identidad de PRAXIS.
- **2FA/TOTP** (`pyotp`): backlog cercano; barato y demandado por gestorías.

### Scopes y permisos

- Scopes por dominio y acción: `finance.calculate`, `calendar.read`, `calendar.write`, `documents.write`, etc.
- `Permission` asocia `tool_name` + `role` a `can_read`, `can_write` y `requires_confirmation`.
- Toda tool declara `permissions_required`; el ejecutor rechaza si el token no los cubre.

## Multi-tenancy

### Aislamiento por RLS

- Todas las tablas tenant-scoped llevan `company_id NOT NULL` y RLS activado.
- Cada conexión fija `app.company_id` desde el `ToolContext` antes de ejecutar.
- Sin contexto, las tablas tenant devuelven cero filas (deny by default).
- Las tablas globales no tienen política y son de solo lectura para tenants.

```sql
ALTER TABLE document ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON document
  USING (company_id = current_setting('app.company_id')::uuid);
```

- Se prueba con `testcontainers[postgres]`: un tenant nunca ve filas de otro.

### Aislamiento en caché

- **Caché compartida** (clima, divisas, geocoding): clave sin `company_id`.
- **Caché operacional** (KPIs, documentos, previsor): clave **incluye** `company_id`.
- Un error de clave de caché es una fuga de datos: se revisa en tests.

### Almacenamiento de documentos

- MVP en el VPS, con nombres opacos (UUID) y ruta fuera del webroot.
- Validación del tipo real con `python-magic` (no por extensión).
- Límite de tamaño y antivirus/escaneo en v2.
- v2: S3/MinIO con URLs firmadas y cifrado en reposo.

## Protección de datos

### Cifrado

- **En tránsito:** TLS obligatorio en producción.
- **En reposo (campos sensibles):** envelope encryption con `cryptography` para `nif`, `salary_gross`, `gross`, `net`, IBAN, tokens OAuth.
- **Rotación de claves:** no se usa `sqlalchemy-utils.EncryptedType`; se implementa sobre cifrado con clave por versión.
- **Secretos de aplicación:** `.env` fuera del repositorio; nunca en git.

### Clasificación

| Clase | Ejemplos | Tratamiento |
|---|---|---|
| `public` | Clima, divisas, unidades, fechas | Sin restricción |
| `business` | Facturas, márgenes, KPIs | RLS + cifrado en exportaciones |
| `personal` | Agenda, NIF, email, teléfono | RLS + cifrado de campos + minimización |
| `sensitive` | Nóminas, salarios, datos de salud | Cifrado de campo + acceso restringido |

### GDPR

- **Base legal y consentimiento:** `DataConsent` por finalidad (`analytics`, `marketing`, `service`).
- **Derecho de acceso y portabilidad:** exportación por `company_id`/`user_id`.
- **Derecho al olvido:** al borrar una empresa se eliminan sus filas tenant (todas con `company_id`); `AuditLog` se anonimiza, no se borra.
- **Minimización:** solo se guardan los datos necesarios para la herramienta.
- **Retención:** política explícita por tabla (ver abajo).
- **Auditoría de acceso a datos personales:** no basta el log de ejecuciones; se registra quién accedió a qué dato personal.

### Retención (propuesta a validar)

| Dato | Retención | Acción |
|---|---|---|
| `ToolExecutionLog` | 12 meses | Borrado o agregación |
| `AuditLog` | 24 meses | Append-only, anonimización |
| `Message` (contenido) | 6 meses | Borrado del contenido, metadatos |
| Documentos | Mientras el tenant exista | Borrado con la empresa |
| Caché operacional | TTL corto | Expiración automática |
| `ConversationContext` | 5 min (Redis) | Expiración |

Estos plazos se documentan como configurables y se validan legalmente (ver [`12-legal-notes.md`](12-legal-notes.md)).

## Herramientas con efectos

- `is_read_only: false` obliga a declarar idempotencia y `idempotency_key`.
- `requires_confirmation: true` en `calendar.create_event`, `documents.generate_invoice` y `alerts.contract_renewal`.
- El ejecutor registra `input_hash` e `idempotency_key` para evitar duplicados por reintentos del agente.
- Las escrituras se validan contra permisos y tenant antes de ejecutar.

## Rate limiting

- `slowapi`/`fastapi-limiter` por usuario, empresa y herramienta.
- Límites alineados con `ToolActivation.limits_override` y con los proveedores externos.
- Protección contra bucles de un agente: presupuesto de llamadas por ventana.

## Auditoría

`ToolExecutionLog` y `AuditLog` registran:

- `request_id`, usuario, empresa, canal.
- Tool, versión, `execution_method`, `cache_hit`, `provider_calls`.
- `success`/`error`, `warnings`, `legal_disclaimer_shown`.
- Para datos personales, acción y recurso accedido.

`asgi-correlation-id` propaga un `request_id` end-to-end en logs (`structlog` en JSON).

## Checklist de seguridad del MVP

- [ ] RLS activo en todas las tablas tenant + tests de aislamiento.
- [ ] API keys hasheadas con Argon2id y nunca logueadas.
- [ ] JWT con expiración y validación de scopes.
- [ ] Cifrado de campos sensibles + gestión de claves.
- [ ] Validación de tipo real de archivos subidos.
- [ ] `requires_confirmation` en tools con efectos.
- [ ] Rate limiting por tenant/tool.
- [ ] Retención y borrado GDPR documentados e implementados.
- [ ] Secretos fuera del repositorio.
- [ ] Dependencias auditadas (`pip-audit` en CI).
